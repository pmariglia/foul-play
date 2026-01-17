from typing import Dict
import numpy as np


def softmax(x, axis=-1):
    x = np.asarray(x)
    x_max = np.max(x, axis=axis, keepdims=True)
    e = np.exp(x - x_max)
    return e / np.sum(e, axis=axis, keepdims=True)


class Player:

    def __init__(self, actions, omega):
        eps = 0.001
        assert len(actions) == len(omega), "Mismatched actions and omega lengths"
        assert all(k >= 1 for k in actions), "Some types have number of actions < 1"
        assert (
                abs(sum(omega) - 1) < eps
        ), f"Omega pdf does not sum to [1 - eps, 1 + eps], eps = {eps}"
        self.n = len(actions)
        self.K = max(actions)
        self.actions = np.array(actions)
        self.omega = np.array(omega)

    def logits(self):
        logits = np.zeros((self.n, self.K))
        for i in range(self.n):
            logits[i, self.actions[i]:] = -np.inf
        return logits


class Solver:

    def __init__(self, p1: Player, p2: Player, payoffs: Dict[[int, int], np.array]):
        self.p1 = p1
        self.p2 = p2
        self.payoffs = payoffs

        self.n1 = p1.n
        self.n2 = p2.n
        self.K1 = p1.K
        self.K2 = p2.K
        self.omega = np.outer(p1.omega, p2.omega)[..., None]
        self.batched_payoffs = np.zeros((self.n1, self.n2, self.K1, self.K2))
        for i in range(self.n1):
            for j in range(self.n2):
                self.batched_payoffs[i, j, 0: p1.actions[i], 0: p2.actions[j]] = (
                    payoffs[i, j]
                )

    def go(self, iterations: int, lr: float, lr_decay: float, p: bool = False):
        p1_logits, p2_logits = self.p1.logits(), self.p2.logits()

        p1_total_policies = np.zeros_like(p1_logits)
        p2_total_policies = np.zeros_like(p2_logits)

        p1_policies = None
        p2_policies = None

        for _ in range(iterations):
            p1_policies = softmax(p1_logits)
            p2_policies = softmax(p2_logits)
            p1_total_policies += p1_policies
            p2_total_policies += p2_policies
            p1_returns = np.einsum("ijmn,jn->ijm", self.batched_payoffs, p2_policies)
            p2_returns = 1 - np.einsum(
                "im,ijmn->ijn", p1_policies, self.batched_payoffs
            )

            # payoff = np.einsum('ijn,jn->ij', p2_returns, p2_policies)[..., None] # mind the negative!
            p1_payoffs = np.einsum("im,ijm->ij", p1_policies, p1_returns)[..., None]
            p2_payoffs = 1 - p1_payoffs

            p1_advantages = p1_returns - p1_payoffs
            p2_advantages = p2_returns - p2_payoffs

            p1_gradient = np.sum(p1_advantages * self.omega, axis=1)
            p2_gradient = np.sum(p2_advantages * self.omega, axis=0)
            # assert p1_gradient.shape == (self.p1.n, self.p1.K)
            # assert p2_gradient.shape == (self.p2.n, self.p2.K)

            p1_logits += lr * p1_gradient
            p2_logits += lr * p2_gradient
            lr *= lr_decay

        return (
            p1_total_policies / iterations,
            p2_total_policies / iterations,
            p1_policies,
            p2_policies,
        )

    def expl(self, p1_policies: np.array, p2_policies: np.array) -> float:
        p1_returns = np.einsum("ijmn,jn->ijm", self.batched_payoffs, p2_policies)
        p2_returns = -np.einsum("im,ijmn->ijn", p1_policies, self.batched_payoffs)
        p1_options = np.sum(self.omega * p1_returns, axis=1)
        p2_options = np.sum(self.omega * p2_returns, axis=0)
        p1_best = np.max(p1_options, axis=1).sum()
        p2_best = np.max(p2_options, axis=1).sum()
        return p1_best + p2_best

    def reward(self, p1_policies: np.array, p2_policies: np.array) -> float:
        r = np.einsum("im,ijmn,jn->ij", p1_policies, self.batched_payoffs, p2_policies)[
            ..., None
        ]
        # print(r.shape)
        # print(self.omega.shape)
        # return r
        return (r * self.omega).sum()


def solve(input_matrices: list[list[list[float]]], iterations: int = 10_000, lr: float = 1.0, lr_decay: float = 1.0):
    """
    Solve a Bayesian game where p1 has 1 type and p2 has multiple types.

    Args:
        input_matrices: List of payoff matrices, one for each p2 type
                       e.g., [matrix_for_p2_type0, matrix_for_p2_type1, ...]
        iterations: Number of iterations for the solver
        lr: Learning rate
        lr_decay: Learning rate decay factor

    Returns:
        Tuple of (p1_average_policy, p2_average_policy, exploitability)
    """
    payoff_matrices = [np.array(m) for m in input_matrices]

    n2 = len(payoff_matrices)

    p2_type_probs = [1.0 / n2] * n2

    assert abs(sum(p2_type_probs) - 1.0) < 0.001, "p2_type_probs must sum to 1"
    assert len(p2_type_probs) == n2, "p2_type_probs length must match number of matrices"

    p1_actions = payoff_matrices[0].shape[0]

    p2_actions = [m.shape[1] for m in payoff_matrices]

    # Create players
    p1 = Player(
        actions=[p1_actions],
        omega=[1.0]
    )

    p2 = Player(
        actions=p2_actions,
        omega=p2_type_probs
    )

    # (0, j) represents p1's single type vs p2's type j
    matrices = {}
    for j in range(n2):
        matrices[(0, j)] = payoff_matrices[j]

    solver = Solver(p1, p2, matrices)

    p1_average, p2_average, p1_last, p2_last = solver.go(
        iterations=iterations,
        lr=lr,
        lr_decay=lr_decay,
    )

    # Calculate exploitability
    exploitability = solver.expl(p1_average, p2_average)

    return [float(i) for i in p1_average[0]], p2_average, exploitability, solver.reward(p1_average, p2_average)