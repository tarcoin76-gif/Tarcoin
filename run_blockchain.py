# run_blockchain.py
"""
Run Tarcoin simple blockchain demo

This script loads src/core/blockchain.py dynamically (importlib) and runs a small
example: creates a Blockchain, adds a transaction, optionally adds a coinbase
reward transaction, and mines a block. Intended for local testing — lowers
difficulty with the --difficulty flag for faster mining.
"""
import os
import time
import importlib.util
import argparse

# Load module from path src/core/blockchain.py without requiring package layout
here = os.path.dirname(__file__)
path = os.path.join(here, "src", "core", "blockchain.py")
if not os.path.exists(path):
    raise FileNotFoundError(f"Could not find blockchain.py at {path}")

spec = importlib.util.spec_from_file_location("blockchain", path)
blockchain_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blockchain_mod)

Blockchain = blockchain_mod.Blockchain
Transaction = blockchain_mod.Transaction


def main(difficulty: int, add_reward: bool):
    bc = Blockchain()

    # Optionally override difficulty for quick testing
    if difficulty is not None:
        bc.difficulty = difficulty

    print("Genesis block:")
    print(bc.get_latest_block().to_dict())

    # Example transaction
    tx = Transaction(
        tx_id="tx1",
        sender="alice",
        receiver="bob",
        amount=10.0,
        timestamp=time.time(),
        nonce=0,
        signature=None,
        fee=0.0
    )

    added = bc.add_transaction(tx)
    print("Transaction added to pending:", added)

    # If requested, add a coinbase/reward transaction so miner receives reward
    if add_reward:
        reward_tx = Transaction(
            tx_id="coinbase-1",
            sender="NETWORK",
            receiver="miner1",
            amount=bc.mining_reward,
            timestamp=time.time(),
            nonce=0,
            signature=None,
            fee=0.0
        )
        # Put reward first in pending txs
        bc.pending_transactions.insert(0, reward_tx)
        print("Added coinbase reward tx to pending:", reward_tx.to_dict())

    print("\nMining pending transactions (may be slow at higher difficulty)...")
    start = time.time()
    new_block = bc.mine_pending_transactions(miner_address="miner1")
    elapsed = time.time() - start

    if new_block:
        print("New block mined in %.2f seconds:" % elapsed)
        print(new_block.to_dict())
    else:
        print("No pending transactions to mine.")

    print("\nChain valid?", bc.is_chain_valid())
    print("Balances:")
    print("  alice:", bc.get_balance("alice"))
    print("  bob:  ", bc.get_balance("bob"))
    print("  miner1:", bc.get_balance("miner1"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Tarcoin simple blockchain demo")
    parser.add_argument("--difficulty", type=int, default=4, help="Set mining difficulty for testing (lower = faster)")
    parser.add_argument("--add-reward", action="store_true", help="Add a coinbase transaction so miner gets the reward")
    args = parser.parse_args()
    main(args.difficulty, args.add_reward)
