import torch
import torch.nn as nn
import torch.nn.functional as F
from Models.networks.sync_batchnorm.batchnorm import SynchronizedBatchNorm2d
from Models.networks.aspp import build_aspp
from Models.networks.decoder import build_decoder
from Models.networks.backbone import build_backbone
from Models.networks.encoder import build_encoderDC

class DeepLab(nn.Module):
    def __init__(self, net_params):
        super(DeepLab, self).__init__()
        backbone = net_params['backbone']
        self.output_stride = net_params['output_stride']
        self.num_classes = net_params['num_classes']
        self.sync_bn = net_params['sync_bn']
        self.num_domain = net_params['num_domain']
        self.num_adaptor = net_params['num_adaptor']
        self.lam = net_params['lam']
        freeze_bn = net_params['freeze_bn']
        
        if backbone == 'drn':
            self.output_stride = 8

        if self.sync_bn == True:
            BatchNorm = SynchronizedBatchNorm2d
        else:
            BatchNorm = nn.BatchNorm2d
        
        self.backbone = build_backbone(backbone, self.output_stride, BatchNorm)
        self.aspp = build_aspp(backbone, self.output_stride, BatchNorm)
        self.decoder = build_decoder(self.num_classes, self.num_adaptor, backbone, BatchNorm)
        # self.last_conv_mask = nn.Sequential(BatchNorm(3),
        #                                     nn.ReLU(),
        #                                     nn.Dropout(0.5),
        #                                     nn.Conv2d(3, self.num_domain, kernel_size=1, stride=1))

        # build encoder for domain feature
        # self.encoder_d = build_encoderDC(BatchNorm)

        if freeze_bn:
            self.freeze_bn()

    # def update_memory(self, feature):
    #     _feature = torch.mean(torch.mean(feature, 3, True), 2, True)
    #     lam = self.lam
    #     self.centroids[0].data = lam * self.centroids[0].data + (1 - lam) * torch.mean(_feature[0:8], 0, True)
    #     self.centroids[1].data = lam * self.centroids[1].data + (1 - lam) * torch.mean(_feature[8:16], 0, True)
    #     self.centroids[2].data = lam * self.centroids[2].data + (1 - lam) * torch.mean(_feature[16:24], 0, True)

    def forward(self, input, extract_feature=False):
        x, low_level_feat = self.backbone(input)

        x, feature = self.aspp(x)
        # max_pooled_d, avg_pooled_d = self.encoder_d(x)
        x, feature, hal_scale, dom_f = self.decoder(x, feature, low_level_feat)

        if extract_feature:
            return feature

        # torch.mean(torch.mean(centroids, 3, True), 2, True)
        # self.update_memory(feature)
        x = F.interpolate(x, size=input.size()[2:], mode='bilinear', align_corners=True)
        
        return x, hal_scale, dom_f

    def freeze_bn(self):
        for m in self.modules():
            if isinstance(m, SynchronizedBatchNorm2d):
                m.eval()
            elif isinstance(m, nn.BatchNorm2d):
                m.eval()

    def freeze_para(self):
        for param in self.backbone.parameters():
            param.requires_grad = False
        # for param in self.aspp.parameters():
        #     param.requires_grad = False


    def get_1x_lr_params(self):
        modules = [self.backbone]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.Conv2d) or isinstance(m[1], SynchronizedBatchNorm2d) \
                        or isinstance(m[1], nn.BatchNorm2d):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p

    def get_10x_lr_params(self):
        modules = [self.aspp, self.decoder]
        for i in range(len(modules)):
            for m in modules[i].named_modules():
                if isinstance(m[1], nn.Conv2d) or isinstance(m[1], SynchronizedBatchNorm2d) \
                        or isinstance(m[1], nn.BatchNorm2d):
                    for p in m[1].parameters():
                        if p.requires_grad:
                            yield p


if __name__ == "__main__":
    model = DeepLab(backbone='mobilenet', output_stride=16)
    model.eval()
    input = torch.rand(1, 3, 513, 513)
    output = model(input)
    print(output.size())


