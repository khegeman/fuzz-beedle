from pytypes.beedle.src.utils.Structs import Pool, Borrow, Loan, Refinance
from pytypes.beedle.src.Lender import Lender
from woke.development.transactions import may_revert
from woke.development.core import Account
from pytypes.beedle.src.utils.Errors import (
    LoanTooLarge,
    LoanTooSmall,
    PoolConfig,
    RateTooHigh,
    AuctionTooShort,
    PoolTooSmall,
    AuctionStarted,
    AuctionNotStarted,
    AuctionNotEnded,
    AuctionEnded,
    TokenMismatch,
)
from woke.development.primitive_types import bytes32, uint
from pytypes.tests.contracts.token import CERC20
from pytypes.solady.src.tokens.ERC20 import ERC20

from wokelib import get_address

# A lot of implementation logic is in this file
from woke.development.core import Address
from dataclasses import dataclass, asdict
from typing import Union, Literal
import math
from .state import *

REQUST_TYPES = Literal["tx", "call"]


def al(pair):
    print("filter pair", pair)
    if pair[1].auctionLength > 100000:
        return True
    return False


def setPool(pool: Pool) -> None:
    id = get_lender().getPoolId(pool.lender, pool.loanToken, pool.collateralToken)
    outstandingLoans = get_lender().pools(id).outstandingLoans
    # we must make sure that we keep the outstanding loans
    pool.outstandingLoans = outstandingLoans
    ret: bytes32 | None = None
    bal = ERC20(pool.loanToken).balanceOf(pool.lender)

    print("balance", type(pool.poolBalance))

    with may_revert(PoolConfig) as e:
        ERC20(pool.loanToken).approve(get_lender(), pool.poolBalance, from_=pool.lender)
        tx = get_lender().setPool(pool, from_=pool.lender)
        poolId = tx.return_value
        print("balance", type(pool.poolBalance))
        # pool_model().insert_or_update(poolId, pool)

        pool_mirror().insert_key(poolId)
        update_pool(poolId)
        # print("pools", len(pool_mirror()))
        ##for p in pool_mirror().filter(lambda pair:  pair[1].auctionLength > 100000):
        #    print(p)

    if e.value is not None:
        print(e.value)

        # should be one of these
        AL = (
            pool.auctionLength == 0
            or pool.auctionLength > get_lender().MAX_AUCTION_LENGTH()
        )
        assert AL
        # sameToken = loanToken == collateralToken
        # assert sameToken


def updateMaxLoanRatio(poolID: bytes32, maxLoanRatio: uint) -> None:
    pool = get_lender().pools(poolID)
    get_lender().updateMaxLoanRatio(poolID, maxLoanRatio, from_=pool.lender)
    # validate then update our local data
    pool = get_lender().pools(poolID)
    assert pool.maxLoanRatio == maxLoanRatio
    # pool_model().insert_or_update(poolID, pool)
    pool_mirror().update()


def updateInterestRate(poolID: bytes32, interestRate: uint) -> None:
    pool = pool_mirror()[poolID]
    get_lender().updateInterestRate(poolID, interestRate, from_=pool.lender)
    # validate then update our local data
    pool = get_lender().pools(poolID)
    assert pool.interestRate == interestRate
    pool_mirror()[poolID] = pool


def borrow(borrower: Account, borr: Borrow) -> None:
    borrows = [borr]
    pool = get_lender().pools(borr.poolId)

    ERC20(pool.collateralToken).approve(get_lender(), borr.collateral, from_=borrower)

    print(borrows)
    bal = ERC20(pool.collateralToken).balanceOf(borrower)

    with may_revert((LoanTooLarge, LoanTooSmall, ERC20.InsufficientBalance)) as e:
        tx = get_lender().borrow(borrows, from_=borrower)
        for ev in tx.events:
            print("borrow", ev)

        loanID = tx.events[4].loanId
        loan = get_lender().loans(loanID)
        loan_mirror().insert_key(loanID)
        loan_mirror()[loanID] = loan
        update_pool(borr.poolId)

    if e.value is not None:
        loan_too_large = borr.debt > pool.poolBalance
        if loan_too_large:
            assert type(e.value) == LoanTooLarge

        loan_too_small = borr.debt < pool.minLoanSize
        if loan_too_small:
            assert type(e.value) == LoanTooSmall

        # some wierd things can happen when loan token == collateral token
        if bal < borr.collateral:
            assert type(e.value) == ERC20.InsufficientBalance


def giveLoan(loan_id: uint, pool_id: bytes32) -> None:
    ##this has to be called by the lender of the loan
    ##and then we need a 2nd pool to give it too
    ##pools must match

    l: Loan = get_lender().loans(loan_id)
    debt = get_lender().getLoanDebt(loan_id)

    with may_revert((RateTooHigh, AuctionTooShort, PoolTooSmall, TokenMismatch)) as e:
        tx = get_lender().giveLoan([loan_id], [pool_id], from_=l.lender)

    pool = get_lender().pools(pool_id)

    if e.value is None:
        l: Loan = get_lender().loans(loan_id)
        loan_mirror()[loan_id] = l

    rateTooHigh = pool.interestRate > l.interestRate
    auctionShort = pool.auctionLength < l.auctionLength
    poolSmall = pool.poolBalance < debt
    LoanTokenMismatch = pool.loanToken != l.loanToken
    ColTokenMismatch = pool.collateralToken != l.collateralToken
    assert (
        rateTooHigh
        or auctionShort
        or poolSmall
        or LoanTokenMismatch
        or ColTokenMismatch
    )


def addToPool(poolID: bytes32, amount: uint) -> None:
    pool = get_lender().pools(poolID)
    bal = ERC20(pool.loanToken).balanceOf(pool.lender)
    with may_revert((ERC20.InsufficientBalance)) as e:
        ERC20(pool.loanToken).approve(get_lender(), amount, from_=pool.lender)
        get_lender().addToPool(poolID, amount, from_=pool.lender)
    if e.value is not None:
        assert bal < amount


def refinance(refinance: Refinance) -> None:
    ##this has to be called by the borrower of the loan
    ##and then we need a 2nd pool to give it too
    ##pools must match

    loan: Loan = get_lender().loans(refinance.loanId)
    pool: Pool = get_lender().pools(refinance.poolId)
    debt = get_lender().getLoanDebt(refinance.loanId)

    if debt > refinance.debt:
        ERC20(pool.loanToken).approve(get_lender(), refinance.debt, from_=loan.borrower)

    else:
        ERC20(pool.collateralToken).approve(
            get_lender(), refinance.collateral, from_=loan.borrower
        )

    print(refinance)

    # we can try to give it
    with may_revert((LoanTooLarge, LoanTooSmall, TokenMismatch)) as e:
        tx = get_lender().refinance([refinance], from_=loan.borrower)
        print("refinance events", tx.events)

    if e.value is None:
        l: Loan = get_lender().loans(refinance.loanId)
        loan_mirror()[refinance.loanId] = l
        update_pool(refinance.poolId)
        set_last_debt(refinance.loanId, loan.debt)

    else:
        if isinstance(e.value, TokenMismatch):
            assert (loan.loanToken != pool.loanToken) or (
                loan.collateralToken != pool.collateralToken
            )
        elif isinstance(e.value, LoanTooLarge):
            assert refinance.debt > pool.poolBalance
        elif isinstance(e.value, LoanTooSmall):
            assert refinance.debt < pool.minLoanSize
        else:
            assert False, "Uncaught error"


def repay(loan_id: uint) -> None:
    loan = loan_mirror()[loan_id]

    print(loan)
    debt = get_lender().getLoanDebt(loan_id)
    # The debt changes every block.  So we need to approve more than we owe
    ERC20(loan.loanToken).approve(get_lender(), debt * 2, from_=loan.borrower)
    with may_revert(ERC20.InsufficientBalance):
        tx = get_lender().repay([loan_id], from_=loan.borrower)
        update_loan(loan_id)


def startAuction(loan_id: uint) -> None:
    loan = loan_mirror()[loan_id]

    with may_revert((AuctionStarted)) as e:
        get_lender().startAuction([loan_id], from_=loan.lender)
    if e.value is not None:
        if type(e) == AuctionStarted:
            assert loan.auctionStartTimestamp < st.MAX_UINT


def zapBuyLoan(loan_id: uint, lender: Account) -> None:
    # it's fine if we already have a pool, this just adjusts it
    # get the existing pool if there is one .  we must preserve the existing outstandingLoans
    loan = loan_mirror()[loan_id]

    id = get_lender().getPoolId(lender, loan.loanToken, loan.collateralToken)
    outstandingLoans = get_lender().pools(id).outstandingLoans

    amount = loan.debt * 2
    CERC20(loan.loanToken).approve(get_lender(), amount, from_=lender)

    p = Pool(
        lender=get_address(lender),
        loanToken=loan.loanToken,
        collateralToken=loan.collateralToken,
        minLoanSize=to_wei(100, "wei"),
        poolBalance=amount,
        maxLoanRatio=2 * 10**18,
        auctionLength=5,
        interestRate=1000,
        outstandingLoans=outstandingLoans,
    )

    with may_revert((AuctionNotStarted, AuctionEnded, RateTooHigh, PoolTooSmall)) as e:
        tx = get_lender().zapBuyLoan(p, loan_id, from_=lender)
        print("zap buy", tx.events)
        poolID = get_lender().getPoolId(lender, loan.loanToken, loan.collateralToken)
        update_loan(loan_id)

    if e.value is not None:
        print("zap failed", e.value)


def seizeLoan(loan_id: uint):
    loan: Loan = get_lender().loans(loan_id)
    with may_revert((AuctionNotStarted, AuctionNotEnded)) as e:
        # anyone can call, but we will use the lender for now
        get_lender().seizeLoan([loan_id], from_=loan.lender)
        update_loan(loan_id)

    if e.value is not None:
        if isinstance(e.value, AuctionNotStarted):
            assert loan.auctionStartTimestamp == st.MAX_UINT
        elif isinstance(e.value, AuctionNotEnded):
            assert (
                default_chain.blocks[-1].timestamp
                < loan.auctionLength + loan.auctionStartTimestamp
            )