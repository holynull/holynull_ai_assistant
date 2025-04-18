"use client";
import { useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKit } from "@reown/appkit/react"
import { useAssistantToolUI } from "@assistant-ui/react";
import { ethers } from 'ethers'
import UniversalProvider from '@walletconnect/universal-provider'
import { useState } from "react";
import { Button, useToast } from '@chakra-ui/react'
import { CopyIcon, CheckIcon, ExternalLinkIcon } from "@chakra-ui/icons"
import { mainnet, bsc, tron, arbitrum, sepolia, solana, solanaTestnet, solanaDevnet } from '@reown/appkit/networks'
import type { AppKitNetwork } from '@reown/appkit-common';
import { wcModal } from "../contexts/appkit";

// Helper function to shorten addresses for display
const shortenAddress = (address: string) => {
	return address ? `${address.substring(0, 6)}...${address.substring(address.length - 4)}` : '';
};

// Toast notification helper function
const showToast = (toast: any, title: string, description: string, status: 'info' | 'warning' | 'success' | 'error', duration: number | null = 5000) => {
	toast.closeAll();
	toast({
		title,
		description,
		status,
		duration,
		isClosable: true,
		position: 'top'
	});
};

// Format number with proper decimals
const formatNumber = (value: number | string, decimals: number = 6): string => {
	const num = typeof value === 'string' ? parseFloat(value) : value;
	if (isNaN(num)) return '0';

	return num.toLocaleString('en-US', {
		minimumFractionDigits: 2,
		maximumFractionDigits: decimals
	});
};

export const useSendEVMTransaction = () => useAssistantToolUI({
	toolName: "send_evm_transaction",
	render: (input) => {
		const [isLoading, setLoading] = useState<boolean>(false);
		const { address, isConnected } = useAppKitAccount()
		const { walletProvider } = useAppKitProvider('eip155')
		const { chainId, switchNetwork } = useAppKitNetwork()
		const { open } = useAppKit();
		const networks: [AppKitNetwork, ...AppKitNetwork[]] = [mainnet, bsc, tron, arbitrum, sepolia, solana];
		const toast = useToast();
		const { txData, name, orderInfo, tx_detail } = input.args;
		const [copySuccess, setCopySuccess] = useState(false);
		const [showRawData, setShowRawData] = useState(false);

		// Extract transaction info from tx_detail
		const extractTransactionInfo = () => {
			try {
				// Parse tx_detail if it's a string
				const txDetailObj = typeof tx_detail === 'string' ? JSON.parse(tx_detail) : tx_detail;

				// Get basic transaction information
				const fromToken = txDetailObj?.from_token_symbol || "Unknown";
				const toToken = txDetailObj?.to_token_symbol || "Unknown";
				const fromAmount = txDetailObj?.from_token_amount || "0";
				const toAmount = txDetailObj?.amount_out_min || txDetailObj?.to_token_amount || "0";
				const fromDecimals = txDetailObj?.from_token_decimals || 18;
				const toDecimals = txDetailObj?.to_token_decimals || 18;

				// Format the amounts with proper decimals
				const formattedFromAmount = parseFloat(fromAmount) / Math.pow(10, parseInt(fromDecimals));
				const formattedToAmount = parseFloat(toAmount) / Math.pow(10, parseInt(toDecimals));

				// Get addresses
				const fromAddress = txDetailObj?.from_address || address || "";
				const toAddress = txDetailObj?.to_address || txData?.to || "";

				// Get network information
				const networkName = networks.find(n => n.id === chainId)?.name || "Unknown Network";
				const networkIcon = getNetworkIcon(networkName);

				// Get other transaction details
				const slippage = txDetailObj?.slippage || "0.5";
				const sourceType = txDetailObj?.source_type || "Unknown";

				// Get exchange rate
				const exchangeRate = formattedFromAmount > 0 ? formattedToAmount / formattedFromAmount : 0;

				return {
					fromToken,
					toToken,
					fromAmount: formattedFromAmount,
					toAmount: formattedToAmount,
					fromAddress,
					toAddress,
					networkName,
					networkIcon,
					slippage,
					sourceType,
					exchangeRate,
					rawData: txDetailObj
				};
			} catch (error) {
				console.error("Error parsing transaction details:", error);
				return {
					fromToken: "Unknown",
					toToken: "Unknown",
					fromAmount: 0,
					toAmount: 0,
					fromAddress: address || "",
					toAddress: txData?.to || "",
					networkName: networks.find(n => n.id === chainId)?.name || "Unknown Network",
					networkIcon: null,
					slippage: "0.5",
					sourceType: "Unknown",
					exchangeRate: 0,
					rawData: null
				};
			}
		};

		// Helper function to get network icon
		const getNetworkIcon = (networkName: string) => {
			switch (networkName.toLowerCase()) {
				case 'ethereum':
				case 'mainnet':
					return '🔷';
				case 'bsc':
				case 'binance smart chain':
					return '🟡';
				case 'arbitrum':
					return '🔵';
				case 'solana':
					return '🟣';
				default:
					return '🌐';
			}
		};

		const transactionInfo = extractTransactionInfo();

		const copyToClipboard = (text: string) => {
			navigator.clipboard.writeText(text)
				.then(() => {
					setCopySuccess(true);
					showToast(toast, 'Copied!', 'Address copied to clipboard', 'success', 2000);
					setTimeout(() => setCopySuccess(false), 2000);
				})
				.catch(err => {
					console.error('Failed to copy: ', err);
					showToast(toast, 'Copy Failed', 'Failed to copy address', 'error');
				});
		};

		const signAndSendTransaction = async () => {
			if (isLoading) return;

			setLoading(true);

			// Check wallet connection
			if (!isConnected) {
				showToast(
					toast,
					'Wallet Connection',
					'Please connect your wallet and try again.',
					'warning'
				);
				await open({ view: "Connect" });
				setLoading(false);
				return;
			}

			try {
				// Switch to correct network
				let curNet = networks.filter(network => network.id === chainId);
				if (curNet && curNet.length > 0) {
					wcModal.switchNetwork(curNet[0]);
					switchNetwork(curNet[0]);
				}

				// Setup provider and signer
				const provider = new ethers.providers.Web3Provider(walletProvider as UniversalProvider)
				const signer = provider.getSigner(address)

				// Prepare transaction data
				let _v = txData.value.indexOf('0x') === 0 ? txData.value : '0x' + txData.value
				let _d = txData.data.indexOf('0x') === 0 ? txData.data : '0x' + txData.data
				const transaction = {
					from: address,
					to: txData.to,
					data: _d,
					value: _v,
					gasLimit: txData.gasLimit,
					gasPrice: txData.gasPrice,
					chainId: chainId as number,
				};

				showToast(
					toast,
					"Confirm Transaction",
					'Please confirm the transaction in your wallet.',
					'warning',
					null
				);

				// Send transaction
				const tx = await signer.sendTransaction(transaction);

				if (tx && name === 'Send Swap Transaction') {
					console.log('Transaction hash:', tx.hash);
					showToast(toast, 'Transaction Sent', 'Transaction successfully sent.', 'success');

					// Generate order record after transaction is sent
					try {
						await fetch(process.env.NEXT_PUBLIC_API_URL + '/generate_swap_order', {
							method: 'POST',
							headers: { 'Content-Type': 'application/json' },
							body: JSON.stringify({
								hash: tx.hash,
								from_token_address: orderInfo.from_token_address,
								to_token_address: orderInfo.to_token_address,
								from_address: orderInfo.from_address,
								to_address: orderInfo.to_address,
								from_token_chain: orderInfo.from_token_chain,
								to_token_chain: orderInfo.to_token_chain,
								from_token_amount: orderInfo.from_token_amount,
								amount_out_min: orderInfo.amount_out_min,
								from_coin_code: orderInfo.from_coin_code,
								to_coin_code: orderInfo.to_coin_code,
								source_type: orderInfo.source_type,
								slippage: orderInfo.slippage
							})
						});

						showToast(toast, 'Order Update', 'Order successfully updated.', 'success');
					} catch (error: any) {
						showToast(
							toast,
							'Order Update Failed',
							error?.message || 'Failed to update order.',
							'error'
						);
						console.error('Error generating swap order:', error);
					}
				} else {
					showToast(toast, 'Transaction Sent', 'Transaction successfully sent.', 'success');
				}

				console.log('Transaction hash:', tx.hash);
			} catch (e: any) {
				showToast(
					toast,
					'Transaction Failed',
					e?.message || 'Failed to process transaction.',
					'error'
				);
				console.error('Transaction error:', e);
			} finally {
				setLoading(false);
			}
		};

		return txData && (
			<div className="rounded-lg border border-gray-200 overflow-hidden bg-white shadow-sm">
				{/* Header */}
				<div className="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-blue-100">
					<div className="flex items-center justify-between">
						<h3 className="text-lg font-semibold text-gray-900">
							{name || "Send Transaction"}
						</h3>
						<div className="text-sm font-medium text-blue-600 px-2 py-1 bg-blue-50 rounded-full">
							{transactionInfo.networkIcon} {transactionInfo.networkName}
						</div>
					</div>
				</div>

				{/* Transaction explanation */}
				<div className="p-4 bg-blue-50 border-b border-blue-200">
					<p className="text-sm text-blue-900">
						<span className="font-semibold text-blue-950">About this transaction:</span> You are about to swap
						{transactionInfo.fromToken ? ` ${formatNumber(transactionInfo.fromAmount)} ${transactionInfo.fromToken} ` : " tokens "}
						for
						{transactionInfo.toToken ? ` ${formatNumber(transactionInfo.toAmount)} ${transactionInfo.toToken}` : " tokens"}.
						Please review the details below before confirming.
					</p>
				</div>

				<div className="p-4">
					<div className="grid gap-4">
						{/* Transaction visualization */}
						<div className="bg-white p-5 rounded-lg border border-gray-200 mb-4">
							<div className="flex items-center justify-between">
								<div className="text-center">
									<div className="text-sm text-gray-500 mb-1">From</div>
									<div className="bg-gray-100 rounded-lg p-3 flex flex-col items-center">
										<div className="font-semibold text-lg text-gray-900">
											{formatNumber(transactionInfo.fromAmount)}
										</div>
										<div className="text-blue-700 font-medium">{transactionInfo.fromToken}</div>
									</div>
								</div>

								<div className="flex-1 px-4 flex justify-center items-center">
									<div className="h-0.5 w-full bg-gray-200 relative">
										<div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white p-2 border border-gray-200 rounded-full">
											<svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
												<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
											</svg>
										</div>
									</div>
								</div>

								<div className="text-center">
									<div className="text-sm text-gray-500 mb-1">To</div>
									<div className="bg-gray-100 rounded-lg p-3 flex flex-col items-center">
										<div className="font-semibold text-lg text-gray-900">
											{formatNumber(transactionInfo.toAmount)}
										</div>
										<div className="text-green-700 font-medium">{transactionInfo.toToken}</div>
									</div>
								</div>
							</div>

							{/* Exchange rate info */}
							<div className="mt-4 text-center">
								<div className="text-xs text-gray-500">Exchange Rate</div>
								<div className="font-medium text-gray-700">
									1 {transactionInfo.fromToken} ≈ {formatNumber(transactionInfo.exchangeRate, 6)} {transactionInfo.toToken}
								</div>
							</div>
						</div>

						{/* Transaction details section */}
						<div className="mt-2">
							<h4 className="text-sm font-semibold text-gray-900 mb-3">Transaction Details</h4>

							<div className="bg-gray-50 p-4 rounded-md border border-gray-200">
								<div className="space-y-3">
									{/* From Token */}
									<div className="flex justify-between items-center border-b border-gray-200 pb-2">
										<span className="text-gray-700 font-medium">You Send</span>
										<div className="flex flex-col items-end">
											<span className="font-semibold text-gray-900">
												{formatNumber(transactionInfo.fromAmount)} {transactionInfo.fromToken}
											</span>
										</div>
									</div>

									{/* To Token */}
									<div className="flex justify-between items-center border-b border-gray-200 pb-2">
										<span className="text-gray-700 font
-medium">You Receive</span>
										<div className="flex flex-col items-end">
											<span className="font-semibold text-gray-900">
												{formatNumber(transactionInfo.toAmount)} {transactionInfo.toToken}
											</span>
											<span className="text-xs text-gray-500">
												Min. received after slippage ({transactionInfo.slippage}%)
											</span>
										</div>
									</div>

									{/* Recipient Address */}
									<div className="flex justify-between items-center border-b border-gray-200 pb-2">
										<span className="text-gray-700 font-medium">Recipient</span>
										<div className="flex items-center space-x-2">
											<span className="text-sm text-gray-800 font-mono bg-gray-100 px-2 py-1 rounded">
												{shortenAddress(transactionInfo.toAddress)}
											</span>
											<button
												onClick={() => copyToClipboard(transactionInfo.toAddress)}
												className="text-gray-500 hover:text-blue-600 transition-colors"
												title="Copy full address"
											>
												{copySuccess ?
													<CheckIcon className="h-4 w-4 text-green-500" /> :
													<CopyIcon className="h-4 w-4" />
												}
											</button>
										</div>
									</div>


									{/* Network */}
									<div className="flex justify-between items-center">
										<span className="text-gray-700 font-medium">Network</span>
										<span className="text-gray-800 font-medium flex items-center space-x-1">
											<span className="text-gray-900">{transactionInfo.networkIcon}</span>
											<span>{transactionInfo.networkName}</span>
										</span>
									</div>
								</div>
							</div>
						</div>

						{/* Security reminders */}
						<div className="bg-amber-50 p-4 rounded-md text-sm text-amber-900 mt-4 border border-amber-200">
							<div className="flex items-start space-x-3">
								<div className="flex-shrink-0">
									<svg className="h-5 w-5 text-amber-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
										<path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
									</svg>
								</div>
								<div>
									<h4 className="font-semibold text-amber-800">Security Reminders:</h4>
									<ul className="mt-2 space-y-2 list-disc pl-5">
										<li>Verify the receiving amount is correct</li>
										<li>Double-check the recipient address</li>
										<li>Ensure you're on the correct network ({transactionInfo.networkName})</li>
										<li>Transaction cannot be reversed once confirmed</li>
									</ul>
								</div>
							</div>
						</div>

						{/* Advanced Details Toggle */}
						<div className="mt-2">
							<button
								onClick={() => setShowRawData(!showRawData)}
								className="text-sm text-gray-600 hover:text-gray-900 flex items-center"
							>
								<span>{showRawData ? 'Hide' : 'Show'} Advanced Details</span>
								<svg
									className={`ml-1 h-4 w-4 transform transition-transform ${showRawData ? 'rotate-180' : ''}`}
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
								</svg>
							</button>

							{showRawData && (
								<div className="mt-2 p-3 bg-gray-50 rounded-md border border-gray-200 overflow-x-auto">
									<pre className="text-xs text-gray-700">
										{JSON.stringify(transactionInfo.rawData, null, 2)}
									</pre>
								</div>
							)}
						</div>

						{/* Action button */}
						<div className="mt-6">
							<Button
								onClick={signAndSendTransaction}
								isDisabled={isLoading}
								colorScheme="blue"
								size="lg"
								className="w-full px-6 py-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-colors duration-200 shadow-sm flex items-center justify-center space-x-2"
							>
								{isLoading ? (
									<>
										<svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
											<circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
											<path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
										</svg>
										<span>Processing...</span>
									</>
								) : (
									<>
										<span>Confirm {name}</span>
										<ExternalLinkIcon className="h-5 w-5" />
									</>
								)}
							</Button>

							<div className="text-xs text-gray-600 mt-2 text-center">
								Click the button to confirm this transaction in your wallet
							</div>
						</div>
					</div>
				</div>
			</div>
		);
	},
});