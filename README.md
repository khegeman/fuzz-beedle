# Stateful Fuzz Test For Beedle Protocol

## Overview

This project was done as an exploration of fuzzing techniques for the Beedle lending protocol during a competitive audit ([CodeHawks | Beedle - Oracle free perpetual lending](https://www.codehawks.com/contests/clkbo1fa20009jr08nyyf9wbx).. 

Beedle is a decentralized lending protocol that allows lending and borrowing without oracles (short background on Beedle).

The fuzz test focuses on testing the core [Lender.sol](https://github.com/Cyfrin/2023-07-beedle/blob/main/src/Lender.sol) contract which contains the logic for pools, loans, and related actions like lending, borrowing, repaying, liquidating etc.

The fuzzing workflow generates randomized test cases to cover different execution paths in Lender.sol. The goal is to find potential issues like bugs, incorrect behavior, or exploits.

The main fuzz test file is [beedle_flow.py](tests/fuzz/beedle_flow.py). It inherits from Woke's FuzzTest class and defines:

- Invariants checked after each test case
- Random data generation strategies
- Flow methods covering all Lender methods

## Usage

To run fuzzing:

1. In a python virtual environment `pip install -r requirements.txt`
2. Generate woke pytypes `woke init pytypes`
3. Run `woke fuzz --passive -n 1 tests/test_beedle.py`
4. Fuzz test cases will be generated and run automatically

The fuzzing will continue generating new test cases until a crash or failed invariant is found.

### Corpus Replay

The fuzz tests record to the `.replay` directory.  To replay a recorded test, the `WOKE_REPLAY` environment variable needs to be set to the name of the recorded test.  

`WOKE_REPLAY=.replay/LenderFuzzTest-20230822-213512.json woke fuzz -n 1 tests/test_beedle.py`

## Structure

The project contains:

- beedle_flow.py - Main fuzz loop and flows
- invariant_impl.py - Invariant check implementations
- flow_impl.py - Flow method implementations
- state.py - Manages test state

The flow and invariant implementations are separated to keep beedle_flow.py concise. 

## Invariants

1. All lenders can withdraw all loan token balances from their respective pools.

2. All loans can be repaid

3. Loan debt is monotonically increasing each block

4. Local copy of loan and pool data matches the data on the smart contract 

## Data Selection

To generate valid data for flows like giveLoan, a "mirror" class is used to track on-chain state locally. This allows implementing filters like:

```python
filtered = pool_mirror().filter(
            lambda pair: (pair[1].loanToken == loan_data.loanToken)
            & (pair[1].collateralToken == loan_data.collateralToken)
           )
```

Which finds all pools compatible with a particular loan.

An extension I created for Woke is to use Hypothesis style generators for random data.  Below is one that selects a random loan and then attempts to find pools with compatible tokens for the loan

```python
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
```

To use the `select_give_loan` with a flow, first create a static member for the generator on the FuzzTest class.  To use the generator with a flow, name the parameter  `select_give_loan`. When the flow is called, it checks for a member with the same name as the parameter and it will call the generator .

```python
    st_give_loan = select_give_loan()

    @flow(precondition=lambda self: LoanCount() > 0 and PoolCount() > 1)
    def giveLoan(self, st_give_loan: GiveLoan) -> None:
        flow_impl.giveLoan(st_give_loan.loan_id, st_give_loan.pool_id)
```

## Future Work

When the contest is complete, I plan to review the findings and determine which can be found via this fuzz test.  I will add invariants to detect more bugs and vulnerabilities. 

## Conclusion

Crafting good fuzz tests for solidity smart contracts is challenging.  Through the process of developing this tests, I ran into 3 issues that I plan to work on improving. 

1. Lack of recording capability of the random input data for inspection and debugging of tests, as well as for reproducibility.

2. Lack of tools to introspect transactions and data through the flows, this makes it difficult to understand why a test failed. 

3. There is a need for test case simplification when running large scale fuzz test with many transacitons.

While working on this project, I created a method to record and replay all fuzz tests.  This is included in my  [wokelib]((https://github.com/khegeman/wokelib) project.  This was a necessary first step before I can work on problems like test case simplification. This tool will analyze recorded results to remove transactions that do not affect the final test case failure. 



## References

- [GitHub - Cyfrin/2023-07-beedle](https://github.com/Cyfrin/2023-07-beedle)
- [GitHub - Ackee-Blockchain/woke: Woke is a Python-based development and testing framework for Solidity.](https://github.com/Ackee-Blockchain/woke)
- [Hypothesis](https://hypothesis.readthedocs.io/en/latest/)
- [GitHub - khegeman/wokelib: A collection of functions for testing solidity contracts](https://github.com/khegeman/wokelib)
