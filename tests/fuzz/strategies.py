from .state import *
from wokelib.generators.random import st
from woke.testing.fuzzing import generators
from eth_utils.currency import to_wei
import random

from wokelib import Mirror, get_address
from pytypes.beedle.src.utils.Structs import Pool, Borrow, Refinance


@dataclass
class GiveLoan:
    loan_id: uint
    pool_id: bytes32

@dataclass
class BuyLoan:
    loan_id: uint
    pool_id: bytes32


def choose_index(model: Mirror):

    """
    This function generates a function that selects an index from the given model for fuzz testing.
    The index is chosen randomly from the available keys in the model.

    Returns:
        function: A function that returns a randomly chosen index when called.
    """
    
    def f():
        return random.choice(list(model.keys()))

    return f


st_pool_amount = st.random_int(min=0, max=to_wei(10, "ether"))

st_pool_id = choose_index(pool_mirror())
st_loan_id = choose_index(loan_mirror())
st_loan_token = st.choose(tokens())
st_collateral_token = st.choose(tokens())


st_auction_length = st.random_int(min=0, max=259200 + 10)
st_lender = st.choose(users())
st_borrower = st.choose(users())


def random_pool():
    """
    This function generates a random pool for fuzz testing. It creates a Pool object with random parameters.
    The lender and loanToken are chosen randomly from the available users and tokens respectively.
    The poolBalance is a random integer between 0 and the balance of the lender.
    The minLoanSize is set to 100 wei.
    The maxLoanRatio is set to 2 * 10**18.
    The auctionLength is a random integer generated by the st_auction_length function.
    The interestRate is set to 1000.
    The outstandingLoans is set to 0.
    
    Returns:
        function: A function that returns a Pool object when called.
    """
    
    def f():
        #todo maxLoanRatio, interest rate, etc should be random . 
        lender = st_lender()
        loanToken: ERC20 = st_loan_token()
        return Pool(
            lender=get_address(lender),
            loanToken=get_address(loanToken),
            collateralToken=get_address(st_loan_token()),
            minLoanSize=to_wei(100, "wei"),
            poolBalance=generators.random_int(min=0, max=loanToken.balanceOf(lender)),
            maxLoanRatio=2 * 10**18,
            auctionLength=st_auction_length(),
            interestRate=1000,
            outstandingLoans=0,
        )

    return f


def random_borrows():
    """
    This function generates a random borrow for fuzz testing. It creates a Borrow object with random parameters.
    The poolId is chosen randomly from the available pool ids.
    The debt is a random integer between the minimum loan size and the pool balance.
    The collateral is calculated based on the debt and the maximum loan ratio.

    Returns:
        function: A function that returns a Borrow object when called.
    """
    
    def f():
        pool_id = st_pool_id()
        pool: Pool = get_lender().pools(pool_id)
        debt = st.random_int(min=pool.minLoanSize, max=pool.poolBalance)()
        return Borrow(
            poolId=pool_id,
            debt=debt,
            collateral=debt * math.ceil(pool.maxLoanRatio / 10**18),
        )

    return f


def select_give_loan():
    """
    This function generates a function that selects a loan to give for fuzz testing.
    The loan_id is chosen randomly from the available loan ids.
    The pool_id is chosen based on the loanToken and collateralToken of the selected loan.
    If no compatible pool is found, a random pool id is chosen.

    Returns:
        function: A function that returns a GiveLoan object when called.
    """
    
    def f():
        loan_id = choose_index(loan_mirror())()
        loan_data = loan_mirror()[loan_id]

        rpools = []

        filtered = pool_mirror().filter(
            lambda pair: (pair[1].loanToken == loan_data.loanToken)
            & (pair[1].collateralToken == loan_data.collateralToken)
        )
        rpools = [k for (k, v) in filtered]
        # if we can't find a compatible pool, pick a pool that will fail and the test will validate failure case
        target_pool = st.choose(rpools)() if len(rpools) > 1 else st_pool_id()
        return GiveLoan(loan_id=loan_id, pool_id=target_pool)

    return f





def select_refinance_loan():
    """
    This function generates a function that selects a loan to refinance for fuzz testing.
    The loan_id is chosen randomly from the available loan ids.
    The pool_id is chosen based on the loanToken and collateralToken of the selected loan.
    If no compatible pool is found, a random pool id is chosen.

    Returns:
        function: A function that returns a Refinance object when called.
    """    
    
    
    
    def f() -> Refinance:
        loan_id = choose_index(loan_mirror())()
        loan_data = loan_mirror()[loan_id]
        filtered = pool_mirror().filter(
            lambda pair: (pair[1].loanToken == loan_data.loanToken)
            & (pair[1].collateralToken == loan_data.collateralToken)
        )
        rpools = [k for (k, v) in filtered]

        # if we can't find a compatible pool, pick a pool that will fail and the test will validate failure case
        target_pool = st.choose(rpools)() if len(rpools) > 1 else st_pool_id()
        pool: Pool = get_lender().pools(target_pool)

        amount = generators.random_int(
            min=0, max=ERC20(loan_data.loanToken).balanceOf(loan_data.borrower)
        )
        collateral = math.ceil((amount * pool.maxLoanRatio) / 10**18)

        return Refinance(
            loanId=loan_id, poolId=target_pool, debt=amount, collateral=collateral
        )

    return f


def select_auction_loan():
    """
    This function generates a function that selects a loan for auction for fuzz testing.
    The loan_id is chosen randomly from the available loan ids where an auction has been started.
    The pool_id is chosen based on the loanToken and collateralToken of the selected loan.
    If no compatible pool is found, a random pool id is chosen.

    Returns:
        function: A function that returns a Refinance object when called.
    """    
    
    def f() -> Refinance:
        # choose from all loans where an auction has been started

        rloans = [
            k
            for (k, v) in loan_mirror().filter(
                lambda pair: pair[1].auctionStartTimestamp < st.MAX_UINT
            )
        ]
        target_loan = st.choose(rloans)() if len(rloans) > 1 else st_loan_id()

        return target_loan

    return f


def select_buy_loan():
    """
    This function generates a function that selects a loan to buy for fuzz testing.
    The loan_id is chosen randomly from the available loan ids where an auction has been started.
    The pool_id is chosen based on the loanToken and collateralToken of the selected loan.
    If no compatible pool is found, a random pool id is chosen.

    Returns:
        function: A function that returns a BuyLoan object when called.
    """
    
    def f():
        loan_id = select_auction_loan()()
        loan_data = loan_mirror()[loan_id]
        filtered = pool_mirror().filter(
            lambda pair: (pair[1].loanToken == loan_data.loanToken)
            & (pair[1].collateralToken == loan_data.collateralToken)
        )
        rpools = [k for (k, v) in filtered]

        # if we can't find a compatible pool, pick a pool that will fail and the test will validate failure case
        target_pool = st.choose(rpools)() if len(rpools) > 1 else st_pool_id()
        return BuyLoan(loan_id=loan_id, pool_id=target_pool)

    return f
    


st_random_pool = random_pool()
st_random_borrow = random_borrows()
st_give_loan = select_give_loan()
