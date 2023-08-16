from .state import *
from .beedle import removeFromPool
import math


def can_removeBalanceFromPool() -> None:
    # if a lender has a balance, they should be able to remove it and get all tokens back
    # this invariant is checked after every flow, but the removal does not persist to the chain.
    # we just want to verify that it is possible to get the full balance back, not actually commit the remove

    for pool_id, pool in pool_mirror().items():
        if pool.poolBalance > 0:
            removeFromPool(pool.lender, pool_id, pool.poolBalance, request_type="call")


def can_repay() -> None:
    # a borrower can always repay his loan (or anyone can repay it)
    # for now, with the invariant a rich benefactor just makes sure we can repay all
    # these are not submitted on chain, just do a gas estimate and see if it reverts

    for loan_id in loan_mirror().keys():
        tx = get_lender().repay([loan_id], request_type="call", from_=owner())


def monotonic_debt() -> None:
    # debt on a loan can not decrease.
    #
    for loan_id in loan_mirror().keys():
        debt = get_lender().getLoanDebt(loan_id)
        assert debt >= get_last_debt(loan_id)
        set_last_debt(loan_id, debt)
