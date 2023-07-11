r"""Tests for the zuko.flows module."""

import pytest
import torch

from torch import randn
from zuko.flows import *


def test_flows(tmp_path):
    flows = [
        GMM(3, 5),
        MAF(3, 5),
        NSF(3, 5),
        SOSPF(3, 5),
        NAF(3, 5),
        UNAF(3, 5),
        CNF(3, 5),
    ]

    for flow in flows:
        # Evaluation of log_prob
        x, c = randn(256, 3), randn(5)
        log_p = flow(c).log_prob(x)

        assert log_p.shape == (256,), flow
        assert log_p.requires_grad, flow

        flow.zero_grad(set_to_none=True)
        loss = -log_p.mean()
        loss.backward()

        for p in flow.parameters():
            assert p.grad is not None, flow

        # Sampling
        x = flow(c).sample((32,))

        assert x.shape == (32, 3), flow

        # Reparameterization trick
        if flow(c).has_rsample:
            x = flow(c).rsample()

            flow.zero_grad(set_to_none=True)
            loss = x.square().sum().sqrt()
            loss.backward()

            for p in flow.parameters():
                assert p.grad is not None, flow

        # Invertibility
        if isinstance(flow, FlowModule):
            x, c = randn(256, 3), randn(256, 5)
            t = flow(c).transform
            z = t.inv(t(x))

            assert torch.allclose(x, z, atol=1e-4), flow

        # Saving
        torch.save(flow, tmp_path / 'flow.pth')

        # Loading
        flow_bis = torch.load(tmp_path / 'flow.pth')

        x, c = randn(3), randn(5)

        seed = torch.seed()
        log_p = flow(c).log_prob(x)
        torch.manual_seed(seed)
        log_p_bis = flow_bis(c).log_prob(x)

        assert torch.allclose(log_p, log_p_bis), flow


def test_autoregressive_transforms():
    ATs = [
        MaskedAutoregressiveTransform,
        NeuralAutoregressiveTransform,
        UnconstrainedNeuralAutoregressiveTransform,
    ]

    for AT in ATs:
        # Without context
        t = AT(3)
        x = randn(3)
        y = t()(x)

        assert y.shape == x.shape, t
        assert y.requires_grad, t
        assert torch.allclose(t().inv(y), x, atol=1e-4), t

        # With context
        t = AT(3, 5)
        x, c = randn(256, 3), randn(5)
        y = t(c)(x)

        assert y.shape == x.shape, t
        assert y.requires_grad, t
        assert torch.allclose(t(c).inv(y), x, atol=1e-4), t

        # Passes

        ## Fully autoregressive
        t = AT(7)
        x = randn(7)
        J = torch.autograd.functional.jacobian(t(), x)

        assert (torch.triu(J, diagonal=1) == 0).all(), t

        ## Coupling
        t = AT(7, passes=2)
        x = randn(7)
        J = torch.autograd.functional.jacobian(t(), x)

        assert (torch.triu(J, diagonal=1) == 0).all(), t
        assert (torch.tril(J[:4, :4], diagonal=-1) == 0).all(), t
        assert (torch.tril(J[4:, 4:], diagonal=-1) == 0).all(), t


def test_coupling_transforms():
    CTs = [
        MaskedCouplingTransform,
    ]

    for CT in CTs:
        # Without context
        t = CT(4)
        x = randn(4)
        z = t()(x)

        assert z.shape == x.shape, t
        assert z.requires_grad, t
        assert torch.allclose(t().inv(z), x, atol=1e-4), t

        # With context
        t = CT(4, 5)
        x, y = randn(256, 4), randn(5)
        z = t(y)(x)

        assert z.shape == x.shape, t
        assert z.requires_grad, t
        assert torch.allclose(t(y).inv(z), x, atol=1e-4), t

        ## Test jacobian
        t = CT(4)
        x = randn(4)
        J = torch.autograd.functional.jacobian(t(), x)

        assert (torch.triu(J, diagonal=1) == 0).all(), t

        assert (torch.tril(J[:2, :2], diagonal=-1) == 0).all(), t
        assert (torch.tril(J[2:, 2:], diagonal=-1) == 0).all(), t