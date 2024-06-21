import requests
import json
import os
from eth_account import Account
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Infura project ID and private key from environment variables
infura_project_id = os.getenv('INFURA_PROJECT_ID')
private_key = os.getenv('PRIVATE_KEY')

# Initialize Web3 provider
w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{infura_project_id}'))

# Check if Web3 is connected
if w3.is_connected():
    print("Web3 is connected")
else:
    raise ConnectionError("Failed to connect to the Ethereum network")

# Inject the POA compatibility middleware to the innermost layer
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Create an account object from the private key
account = Account.from_key(private_key)
print("Account Address:", account.address)

# Check the account balance
balance = w3.eth.get_balance(account.address)
print("Account Balance:", w3.from_wei(balance, 'ether'), "ETH")

# Uniswap V2 Router contract address
uniswap_router_address = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'

# Load the ABI from the JSON file
with open('uniswap_v2_router_abi.json', 'r') as abi_file:
    uniswap_router_abi = json.load(abi_file)

# Create contract instance
uniswap_router = w3.eth.contract(address=uniswap_router_address, abi=uniswap_router_abi)

def get_gas_fee_data():
    # Get gas fee data
    gas_fee_data = w3.eth.fee_history(1, 'latest', reward_percentiles=[50])
    max_fee_per_gas = gas_fee_data['baseFeePerGas'][-1] + gas_fee_data['reward'][-1][0]
    max_priority_fee_per_gas = gas_fee_data['reward'][-1][0]
    return max_fee_per_gas, max_priority_fee_per_gas

def increment_gas_fees(max_fee_per_gas, max_priority_fee_per_gas, increment=10**9):
    return max_fee_per_gas + increment, max_priority_fee_per_gas + increment

def buy_token(token_address, eth_amount):
    # Get nonce
    nonce = w3.eth.get_transaction_count(account.address)

    # Get gas fee data
    max_fee_per_gas, max_priority_fee_per_gas = get_gas_fee_data()
    max_fee_per_gas, max_priority_fee_per_gas = increment_gas_fees(max_fee_per_gas, max_priority_fee_per_gas)

    # Transaction details
    tx = uniswap_router.functions.swapExactETHForTokens(
        0,  # Accept any amount of tokens
        [w3.to_checksum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'), w3.to_checksum_address(token_address)], 
        account.address, 
        (w3.eth.get_block('latest')['timestamp'] + 10000)
    ).build_transaction({
        'from': account.address,
        'value': w3.to_wei(eth_amount, 'ether'),
        'nonce': nonce,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': max_priority_fee_per_gas
    })

    # Estimate gas limit
    gas_limit = w3.eth.estimate_gas(tx)
    tx['gas'] = gas_limit

    # Sign transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)

    # Send transaction
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

def sell_token(token_address, token_amount):
    # Approve Uniswap Router to spend the token
    token_contract = w3.eth.contract(address=token_address, abi=uniswap_router_abi)
    nonce = w3.eth.get_transaction_count(account.address)

    # Get gas fee data
    max_fee_per_gas, max_priority_fee_per_gas = get_gas_fee_data()
    max_fee_per_gas, max_priority_fee_per_gas = increment_gas_fees(max_fee_per_gas, max_priority_fee_per_gas)

    # Approve transaction
    approve_tx = token_contract.functions.approve(
        uniswap_router_address, 
        token_amount
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': max_priority_fee_per_gas
    })

    # Estimate gas limit for approval
    gas_limit_approve = w3.eth.estimate_gas(approve_tx)
    approve_tx['gas'] = gas_limit_approve

    # Sign and send the approve transaction
    signed_approve_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
    w3.eth.send_raw_transaction(signed_approve_tx.rawTransaction)
    w3.eth.wait_for_transaction_receipt(signed_approve_tx.hash)

    # Get nonce again after approval
    nonce = w3.eth.get_transaction_count(account.address)

    # Transaction details
    tx = uniswap_router.functions.swapExactTokensForETH(
        token_amount,  # Amount of tokens to sell
        0,  # Accept any amount of ETH
        [w3.to_checksum_address(token_address), w3.to_checksum_address('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')], 
        account.address, 
        (w3.eth.get_block('latest')['timestamp'] + 10000)
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': max_priority_fee_per_gas
    })

    # Estimate gas limit for swap
    gas_limit_swap = w3.eth.estimate_gas(tx)
    tx['gas'] = gas_limit_swap

    # Sign transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key)

    # Send transaction
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    # Wait for transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

# Example usage of buy and sell functions
token_address = '0x69babE9811CC86dCfC3B8f9a14de6470Dd18EDA4'  # Replace with the actual token address
eth_amount = 0.00001  # Amount of ETH to swap for tokens
token_amount = 100  # Amount of tokens to swap for ETH

# Buy tokens
buy_receipt = buy_token(token_address, eth_amount)
print("Buy Transaction Receipt:", buy_receipt)

# Sell tokens
# sell_receipt = sell_token(token_address, token_amount)
# print("Sell Transaction Receipt:", sell_receipt)
