import torch
import torch.nn as nn

import model.utils as utils

import torchcde

class Scaler(nn.Module):
    '''
    A Neural CDE Locator.

    Ref: https://github.com/patrick-kidger/torchcde/blob/master/example/time_series_classification.py
    '''
    def __init__(self, input_dim, latent_dim, output_dim, device):
        super(Scaler, self).__init__()
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.n_cnn_intervals = 2048
        self.device = device

        self.initial = nn.Sequential(
            # nn.LayerNorm(input_dim),
            utils.create_net(input_dim, latent_dim, n_layers=0, n_units=1024, nonlinear=nn.PReLU),
            # *[utils.ResBlock(1024, 1024, nonlinear=nn.PReLU) for i in range(3)],
            # utils.create_net(1024, latent_dim, n_layers=0, n_units=1024, nonlinear=nn.PReLU),
        )
        
        self.gate = nn.PReLU()

        self.cnn_featurizer = nn.Sequential(
            nn.Conv1d(latent_dim, 256, kernel_size=15, stride=2, padding=7), nn.PReLU(),
            nn.Conv1d(256, 512, kernel_size=15, stride=2, padding=7), nn.PReLU(),
            *[utils.CNNResBlock(512, 128, nonlinear=nn.PReLU, layernorm=True) for i in range(15)],
            nn.Conv1d(512, 128, kernel_size=15, stride=2, padding=7), nn.PReLU(),
            nn.Conv1d(128, 64, kernel_size=15, stride=2, padding=7), nn.PReLU(),
            nn.Conv1d(64, 32, kernel_size=1, stride=1, padding=0), nn.PReLU(),
        )
        utils.init_network_weights(self.cnn_featurizer, nn.init.kaiming_normal_)

        self.regressor = nn.Sequential(
            nn.Linear(128 * 32, output_dim)
        )
        
       
    def forward(self, coeffs):
        X = torchcde.CubicSpline(coeffs)

        # X0 = X.evaluate(X.interval[0])
        # z0 = self.initial(X0)

        # X1 = X.evaluate(X.interval[-1])
        # z1 = self.initial(X1)

        interval = torch.linspace(X.interval[0], X.interval[-1], self.n_cnn_intervals).to(self.device)

        # z_T = torchcde.cdeint(X=X,
        #                       z0=z0,
        #                       func=self.cde_func,
        #                       t=interval,
        #                       adjoint=False,
        #                       method="dopri5", rtol=1e-5, atol=1e-7)

        # z_T1 = torchcde.cdeint(X=X,
        #                       z0=z1,
        #                       func=self.cde_func_r,
        #                       t=torch.flip(interval, dims=[0]),
        #                       adjoint=False,
        #                       method="dopri5", rtol=1e-5, atol=1e-7)

        # z = self.gate(z_T + torch.flip(z_T1, dims=[0])) + self.initial(X.evaluate(interval))
        # print(X.evaluate(interval).shape)
        z = self.initial(X.evaluate(interval))
        z = z.transpose(-1, -2) # (batch, time, channel) -> (batch, channel, time)

        z = self.cnn_featurizer(z).flatten(start_dim=1)

        z = self.regressor(z)

        return z