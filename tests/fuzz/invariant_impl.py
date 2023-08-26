from .state import *
from .beedle import removeFromPool
import math


def can_removeBalanceFromPool() -> None:
    """Check if balance can be removed from the pool.
    
    Verifies that a lender with a balance greater than zero can remove their balance from the pool.
    This function does not commit the removal to the blockchain, but rather checks that it's possible.

    Note:
        This invariant is checked after every flow.
    """
    for pool_id, pool in pool_mirror().items():
        if pool.poolBalance > 0:
            removeFromPool(pool.lender, pool_id, pool.poolBalance, request_type="call")


def can_repay() -> None:
    """Check if a loan can be repaid.
    
    Confirms that a borrower can always repay their loan.
    This function does not actually repay the loan, but performs a gas estimate to check if it would revert.

    Note:
        For now, this function assumes a rich benefactor can repay all.
    """
    for loan_id in loan_mirror().keys():
        tx = get_lender().repay([loan_id], request_type="call", from_=owner())


def monotonic_debt() -> None:
    """Check if loan debt is monotonic.
    
    Asserts that the debt on a loan can never decrease over time.
    
    Raises:
        AssertionError: If debt decreases.
    """
    for loan_id in loan_mirror().keys():
        debt = get_lender().getLoanDebt(loan_id)
        assert debt >= get_last_debt(loan_id)
        set_last_debt(loan_id, debt)

def mirror_match() -> None:
    """Check if loan debt is monotonic.
    
    Asserts that the debt on a loan can never decrease over time.
    
    Raises:
        AssertionError: If debt decreases.
    """
    loan_mirror().assert_equals_remote()
    pool_mirror().assert_equals_remote()
