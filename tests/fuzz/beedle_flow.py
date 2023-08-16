# flow test for beedle protocol

from woke.development.core import Address, Account
from eth_utils.currency import to_wei
from woke.testing.fuzzing import invariant, flow
from woke.development.primitive_types import uint, bytes32

from pytypes.beedle.src.Lender import Lender
from pytypes.beedle.src.utils.Structs import Pool, Borrow, Loan, Refinance


from wokelib import collector

from .beedle import (
    removeFromPool,
    getLoanDebt,
)


import os
from wokelib.generators.random import st

Replay = int(os.getenv("WOKE_REPLAY", 0)) > 0

if Replay:
    from wokelib.generators.replay import fuzz_test
else:
    from wokelib.generators.random import fuzz_test


# stateful fuzz test for flows

from .state import *
from .strategies import *
from . import invariant_impl
from . import flow_impl


class LenderFuzzTest(
    fuzz_test.FuzzTest  # pyright: ignore [reportGeneralTypeIssues]
):
    # random data generation strategies
    st_pool_amount = st.random_int(min=0, max=to_wei(10, "ether"))
    st_loan_amount = st.random_int(min=0, max=to_wei(1, "ether"))

    st_auction_length = st.random_int(min=0, max=259200 + 10)
    st_interest_rate = st.random_int(min=10000, max=20000)
    st_max_loan_ratio = st.random_int(min=2 * 10**18, max=3 * 10**18)
    st_lender = st.choose(users())
    st_borrower = st.choose(users())
    st_pool_id = choose_index(pool_mirror())
    st_loan_token = st.choose(tokens())
    st_collateral_token = st.choose(tokens())
    st_random_pool = random_pool()
    st_random_borrow = random_borrows()
    st_give_loan = select_give_loan()
    st_refinance_loan = select_refinance_loan()
    st_loan_id = choose_index(loan_mirror())

    st_auction_loan = select_auction_loan()
    st_auction_started = select_auction_loan()

    # @default_chain.snapshot_and_revert()
    @invariant(period=1)
    def can_removeBalanceFromPool(self) -> None:
        invariant_impl.can_removeBalanceFromPool()

    @invariant(period=1)
    def can_repay(self) -> None:
        invariant_impl.can_repay()

    @invariant(period=1)
    def monotonic_debt(self) -> None:
        invariant_impl.monotonic_debt()

    @collector()
    def pre_sequence(self) -> None:
        tokenCount = 2
        initialize(tokenCount)

    @flow()
    def setPool(self, st_random_pool: Pool) -> None:
        flow_impl.setPool(st_random_pool)

    @flow(precondition=lambda self: PoolCount() > 0)
    def borrow(self, st_borrower: Account, st_random_borrow: Borrow) -> None:
        flow_impl.borrow(st_borrower, st_random_borrow)

    @flow(precondition=lambda self: PoolCount() > 0)
    def addToPool(self, st_pool_id: bytes32, st_pool_amount: uint) -> None:
        flow_impl.updateMaxLoanRatio(st_pool_id, st_pool_amount)

    @flow(precondition=lambda self: LoanCount() > 0)
    def repay(self, st_loan_id: uint) -> None:
        flow_impl.repay(st_loan_id)

    @flow(precondition=lambda self: LoanCount() > 0 and PoolCount() > 1)
    def giveLoan(self, st_give_loan: GiveLoan) -> None:
        flow_impl.giveLoan(st_give_loan.loan_id, st_give_loan.pool_id)

    @flow(precondition=lambda self: LoanCount() > 0)
    def startAuction(self, st_loan_id: uint) -> None:
        flow_impl.startAuction(st_loan_id)

    @flow(precondition=lambda self: LoanCount() > 0, weight=0)
    def buyLoan(self, st_auction_loan: uint):
        # flow_impl.buyLoan(st_auction_loan)
        pass

    @flow(precondition=lambda self: LoanCount() > 0, weight=0)
    def zapBuyLoan(self, st_auction_loan: uint, st_lender: Account):
        flow_impl.zapBuyLoan(st_auction_loan, st_lender)

    @flow(precondition=lambda self: LoanCount() > 0)
    def seizeLoan(self, st_auction_started: uint):
        flow_impl.seizeLoan(st_auction_started)

    @flow(precondition=lambda self: LoanCount() > 0 and PoolCount() > 1)
    def refinance(self, st_refinance_loan: Refinance) -> None:
        flow_impl.refinance(st_refinance_loan)

    @flow(precondition=lambda self: PoolCount() > 0)
    def updateMaxLoanRatio(self, st_pool_id: bytes32, st_max_loan_ratio: uint) -> None:
        flow_impl.updateMaxLoanRatio(st_pool_id, st_max_loan_ratio)

    @flow(precondition=lambda self: PoolCount() > 0)
    def updateInterestRate(self, st_pool_id: bytes32, st_interest_rate: uint) -> None:
        flow_impl.updateInterestRate(st_pool_id, st_interest_rate)
