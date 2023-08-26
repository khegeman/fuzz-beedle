"""
Implementations of core lending protocol flows for fuzz testing.

This module contains the logic for executing flows like:

- Setting pools
- Borrowing 
- Repaying
- Giving loans
- Starting auctions
- Buying loans
- Refinancing
- Seizing collateral

The flows call the Lender contract and validate the results.

Flows are designed to be easily composed in sequence by the fuzzer.

Key functions:

- setPool: Creates a new lending pool.
- updateMaxLoanRatio: Updates the max loan ratio for a lending pool.
- updateInterestRate: Updates the interest rate for a lending pool.
- borrow: Borrows tokens from a pool.
- giveLoan: Transfers a loan between pools.
- addToPool: Adds more tokens to increase a pool's liquidity.
- refinance: Moves a loan to a new pool.
- repay: Repays debt on a loan. 
- startAuction: Starts an auction on a loan.
- buyLoan: Buys a loan at auction.
- zapBuyLoan: Buys a loan while opening a compatible lending pool.
- seizeLoan: Seizes collateral after an auction.

Helper functions like getPoolId handle common logic.

Reverts are caught and validated using Woke's may_revert decorator.

The state module is used to track loans, pools, and approvals.
"""

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
    RatioTooHigh
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

from .beedle import getPoolID 


def setPool(pool: Pool) -> None:
    """
    Creates a new lending pool.
    
    :param pool: A Pool object containing pool configuration details.
    """

    id = get_lender().getPoolId(pool.lender, pool.loanToken, pool.collateralToken)
    outstandingLoans = get_lender().pools(id).outstandingLoans
    # we must make sure that we keep the outstanding loans
    pool.outstandingLoans = outstandingLoans
    ret: bytes32 | None = None
    bal = ERC20(pool.loanToken).balanceOf(pool.lender)

    with may_revert(PoolConfig) as e:
        ERC20(pool.loanToken).approve(get_lender(), pool.poolBalance, from_=pool.lender)
        tx = get_lender().setPool(pool, from_=pool.lender)
        poolId = tx.return_value


        pool_mirror()[poolId]=pool
        pool_mirror().assert_equals_remote()

    if e.value is not None:

        # should be one of these
        AL = (
            pool.auctionLength == 0
            or pool.auctionLength > get_lender().MAX_AUCTION_LENGTH()
        )
        assert AL
        # sameToken = loanToken == collateralToken
        # assert sameToken


def updateMaxLoanRatio(poolID: bytes32, maxLoanRatio: uint) -> None:
    """
    Updates the maximum loan ratio for a lending pool.
    
    :param poolID: The ID of the lending pool.
    :param maxLoanRatio: The new maximum loan-to-collateral ratio.
    """
    pool = get_lender().pools(poolID)
    get_lender().updateMaxLoanRatio(poolID, maxLoanRatio, from_=pool.lender)
    # validate then update our local data
    pool = get_lender().pools(poolID)
    assert pool.maxLoanRatio == maxLoanRatio
    pool_mirror().update()


def updateInterestRate(poolID: bytes32, interestRate: uint) -> None:
    """
    Updates the interest rate for a lending pool.
    
    :param poolID: The ID of the lending pool.
    :param interestRate: The new interest rate for the loans in the pool.
    """
    pool = pool_mirror()[poolID]
    get_lender().updateInterestRate(poolID, interestRate, from_=pool.lender)
    # validate then update our local data
    pool = get_lender().pools(poolID)
    assert pool.interestRate == interestRate
    pool_mirror()[poolID] = pool


def borrow(borrower: Account, borr: Borrow) -> None:
    """
    Borrows tokens from a lending pool.
    
    :param borrower: The account of the borrower.
    :param borr: A Borrow object containing borrowing details.
    """
    borrows = [borr]
    pool = get_lender().pools(borr.poolId)

    ERC20(pool.collateralToken).approve(get_lender(), borr.collateral, from_=borrower)


    bal = ERC20(pool.collateralToken).balanceOf(borrower)

    with may_revert((LoanTooLarge, LoanTooSmall, ERC20.InsufficientBalance)) as e:
        tx = get_lender().borrow(borrows, from_=borrower)

        loanID = tx.events[4].loanId

        loan = get_lender().loans(loanID)
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
    """
    Transfers a loan between compatible pools.
    
    :param loan_id: The ID of the loan to be transferred.
    :param pool_id: The ID of the target lending pool.
    """
    
    l: Loan = get_lender().loans(loan_id)
    debt = get_lender().getLoanDebt(loan_id)

    with may_revert((RateTooHigh, AuctionTooShort, PoolTooSmall, TokenMismatch)) as e:
        tx = get_lender().giveLoan([loan_id], [pool_id], from_=l.lender)

    pool = get_lender().pools(pool_id)

    rateTooHigh = pool.interestRate > l.interestRate
    auctionShort = pool.auctionLength < l.auctionLength
    poolSmall = pool.poolBalance < debt
    LoanTokenMismatch = pool.loanToken != l.loanToken
    ColTokenMismatch = pool.collateralToken != l.collateralToken

    if e.value is None:
        l: Loan = get_lender().loans(loan_id)
        loan_mirror()[loan_id] = l
        #we should just update the pools involved.  For now update all
        pool_mirror().update()
        
    elif isinstance(e.value,RateTooHigh):
        assert(rateTooHigh)
    elif isinstance(e.value,AuctionTooShort):
        assert(auctionShort)
    elif isinstance(e.value,PoolTooSmall):
        assert(poolSmall)        
    elif isinstance(e.value,TokenMismatch):
        assert(LoanTokenMismatch or ColTokenMismatch)
    else:
        raise "Unknown reason for revert"


def addToPool(poolID: bytes32, amount: uint) -> None:
    """
    Increases a lending pool's liquidity by adding tokens.
    
    :param poolID: The ID of the lending pool.
    :param amount: The amount of tokens to add to the pool.
    """
    
    pool = get_lender().pools(poolID)
    bal = ERC20(pool.loanToken).balanceOf(pool.lender)
    with may_revert((ERC20.InsufficientBalance)) as e:
        ERC20(pool.loanToken).approve(get_lender(), amount, from_=pool.lender)
        get_lender().addToPool(poolID, amount, from_=pool.lender)
    if e.value is not None:
        assert bal < amount


def refinance(refinance: Refinance) -> None:
    """
    Moves a loan to a new lending pool with different terms.
    
    :param refinance: A Refinance object containing refinance details.
    """
    loan: Loan = get_lender().loans(refinance.loanId)
    pool: Pool = get_lender().pools(refinance.poolId)
    debt = get_lender().getLoanDebt(refinance.loanId)

    tx=None
    with default_chain.change_automine(False):
        if debt > refinance.debt:
            ERC20(pool.loanToken).approve(get_lender(), debt, from_=loan.borrower,confirmations=0, gas_limit="auto")

        else:
            atx = ERC20(pool.collateralToken).approve(
                get_lender(), refinance.collateral, from_=loan.borrower,confirmations=0, gas_limit="auto"
            )


        eTokenMismatch = (loan.loanToken != pool.loanToken) or (
                loan.collateralToken != pool.collateralToken
            )
        eLoanTooLarge = refinance.debt > pool.poolBalance
        eLoanTooSmall = refinance.debt > pool.poolBalance 
        eInsufficientBalance = (ERC20(pool.loanToken).balanceOf(loan.borrower) < debt - refinance.debt) if debt > refinance.debt else (ERC20(pool.collateralToken).balanceOf(loan.borrower) < refinance.collateral)
        eRatioTooHigh = math.ceil((refinance.debt * 10 ** 18) / refinance.collateral) > pool.maxLoanRatio
        shouldRevert = any([eTokenMismatch,eLoanTooLarge,eLoanTooSmall])
        
        try:
            tx = get_lender().refinance([refinance], from_=loan.borrower,confirmations=0, gas_limit="auto")
        except TokenMismatch:
            assert eTokenMismatch
        except LoanTooLarge:
                assert eLoanTooLarge
        except LoanTooSmall:
                assert eLoanTooSmall
        except  ERC20.InsufficientBalance:
            assert eInsufficientBalance 
        except RatioTooHigh:
            assert eRatioTooHigh             
        else:

            assert not shouldRevert
    
   
    
    default_chain.mine()
    
    if tx is not None:
        if tx.error is None:
            l: Loan = get_lender().loans(refinance.loanId)
            loan_mirror()[refinance.loanId] = l
            update_pool(refinance.poolId)
            set_last_debt(refinance.loanId, l.debt)
            pool_mirror().update()        




def repay(loan_id: uint) -> None:
    """
    Repays all debt on a loan.
    
    :param loan_id: The ID of the loan to be fully repaid.
    """ 
    loan = loan_mirror()[loan_id]

    # The debt changes every block.  So we need to approve more than we owe

    #debt changes every block, so it's best if we approve and repay in the same block
    with default_chain.change_automine(False):
        debt = get_lender().getLoanDebt(loan_id)        
        ERC20(loan.loanToken).approve(get_lender(), debt*2, from_=loan.borrower,confirmations=0, gas_limit="auto")
        with may_revert((ERC20.InsufficientBalance)) as e:
            tx = get_lender().repay([loan_id], from_=loan.borrower,confirmations=0, gas_limit="auto")

    default_chain.mine()
    if e.value is None:
        update_loan(loan_id)
        pool_mirror().update()    
    elif isinstance(e.value,ERC20.InsufficientBalance):
        assert(ERC20(loan.loanToken).balanceOf(loan.borrower) < debt)
        

def startAuction(loan_id: uint) -> None:
    """
    Initiates an auction for a loan.
    
    :param loan_id: The ID of the loan for which the auction should start.
    """
    
    loan = loan_mirror()[loan_id]

    with may_revert((AuctionStarted)) as e:
        get_lender().startAuction([loan_id], from_=loan.lender)
        loan_mirror()[loan_id].auctionStartTimestamp = default_chain.blocks[-1].timestamp
        assert get_lender().loans(loan_id).auctionStartTimestamp == default_chain.blocks[-1].timestamp
    if e.value is not None:
        if type(e) == AuctionStarted:
            assert loan.auctionStartTimestamp < st.MAX_UINT
    

def buyLoan(loan_id: uint, pool_id: bytes32, lender: Account) -> None:
    """
    Buys a loan in an ongoing auction.
    
    :param loan_id: The ID of the loan to be purchased.
    :param pool_id: The ID of the lending pool associated with the loan.
    :param lender: The account of the buyer (lender).
    """    
    loan = loan_mirror()[loan_id]
    
    oldPool = getPoolID(loan)
    with may_revert((AuctionNotStarted, AuctionEnded, RateTooHigh, PoolTooSmall)) as e:
        tx = get_lender().buyLoan(loan_id,pool_id, from_=lender)
    
        update_loan(loan_id)
        newPool = getPoolID(loan_mirror()[loan_id])
        #easy way to detect bug = make sure new poold id matches one passed
        assert newPool == pool_id
        update_pool(oldPool)
        update_pool(newPool)


def zapBuyLoan(loan_id: uint, lender: Account) -> None:
    """
    Buys a loan while setting up a compatible lending pool.
    
    :param loan_id: The ID of the loan to be purchased.
    :param lender: The account of the buyer (lender).
    """

    # it's fine if we already have a pool, this just adjusts it
    # get the existing pool if there is one .  we must preserve the existing outstandingLoans
    loan = loan_mirror()[loan_id]
    oldPool = getPoolID(loan)
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
        poolID = get_lender().getPoolId(lender, loan.loanToken, loan.collateralToken)
        update_loan(loan_id)
        update_pool(oldPool)
        update_pool(id)



def seizeLoan(loan_id: uint):
    """
    Seizes collateral after an auction ends without a buyer.
    
    :param loan_id: The ID of the loan for which collateral should be seized.
    """
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

