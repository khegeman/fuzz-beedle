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
    def f():
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
    def f() -> Refinance:
        # choose from all loans where an auction has been started

        rloans = [
            k
            for (k, v) in loan_mirror().filter(
                lambda pair: pair[1].auctionStartTimestamp < st.MAX_UINT
            )
        ]
        print("rloans", rloans)
        target_loan = st.choose(rloans)() if len(rloans) > 1 else st_loan_id()
        print("target", target_loan, len(rloans))

        return target_loan

    return f


def select_buy_loan():
    def f():
        loan_id = select_auction_loan()()
        loan_data = loan_mirror()[loan_id]

        rpools = []

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
