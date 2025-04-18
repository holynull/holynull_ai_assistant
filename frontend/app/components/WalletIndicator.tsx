"use client";
import { add } from "date-fns";
import { Tooltip } from "@radix-ui/react-tooltip";
import { TooltipIconButton } from "./ui/assistant-ui/tooltip-icon-button";
import { Wallet } from "lucide-react";
import { useAppKit, useAppKitAccount, useAppKitNetwork } from "@reown/appkit/react";
import { FC, useEffect, useState } from "react";
const NETWORK_CHAIN_ID_MAP = {
	"1": "Ethereum",
	"56": "BSC",
	"137": "Polygon",
	"42161": "Arbitrum",
	"10": "Optimism",
	"5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp": "Solana"
}

export const WalletIndicator: FC<{}> = () => {
	const { open, close } = useAppKit();
	const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
	const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()

	// 确保初始状态为 'disconnected'，防止服务器/客户端不匹配
	const [walletStatus, setWalletStatus] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
	const [isClient, setIsClient] = useState(false);



	// 在组件挂载后更新状态
	useEffect(() => {
		setIsClient(true);
		setWalletStatus(isConnected ? 'connected' : 'disconnected');
	}, [isConnected]);
	// 更新连接钱包函数
	const connectWallet = async () => {
		try {
			setWalletStatus('connecting');
			await open({ view: "Connect" });
			// AppKit会自动更新isConnected状态
		} catch (error) {
			setWalletStatus('error');
			// 添加错误处理
			console.error("Failed to connect wallet:", error);
		}
	}

	// 在useEffect中监听连接状态变化
	useEffect(() => {
		setWalletStatus(isConnected ? 'connected' : 'disconnected');
	}, [isConnected]);
	// 添加选中状态管理
	const [isSelected, setIsSelected] = useState(false);

	const formattedAddress = address ?
		window.innerWidth < 768 ?
			`${address.substring(0, 8)}...${address.substring(address.length - 6)}` :
			`${address.substring(0, 6)}...${address.substring(address.length - 4)}` : '';

	const [tooltipContent, setTooltipContent] = useState('Connect your wallet');

	useEffect(() => {
		if (status === 'connected') {
			setTooltipContent(`Addr: ${formattedAddress} (${NETWORK_CHAIN_ID_MAP[chainId as keyof typeof NETWORK_CHAIN_ID_MAP] || 'Unknown Network'}, Chain ID: ${chainId || '?'}) `);
		} else {
			setTooltipContent('Connect your wallet');
		}
	}, [status, formattedAddress, chainId]);

	const statusConfig = {
		'disconnected': {
			buttonClass: 'text-slate-400 hover:text-slate-600',
			bgClass: 'bg-transparent hover:bg-slate-100',
			selectedBgClass: 'bg-slate-100',
			iconColor: 'text-slate-400',
			statusIndicator: null,
			label: 'Connect'
		},
		'connecting': {
			buttonClass: 'text-amber-500 hover:text-amber-600',
			bgClass: 'bg-transparent hover:bg-amber-50',
			selectedBgClass: 'bg-amber-50',
			iconColor: 'text-amber-500',
			statusIndicator: <div className="h-2 w-2 animate-pulse rounded-full bg-amber-500"></div>,
			label: 'Connecting...'
		},
		'connected': {
			buttonClass: 'text-green-500 hover:text-green-600',
			bgClass: 'bg-transparent hover:bg-green-50',
			selectedBgClass: 'bg-green-50',
			iconColor: 'text-green-500',
			statusIndicator: <div className="h-2 w-2 rounded-full bg-green-500"></div>,
			label: formattedAddress
		},
		'error': {
			buttonClass: 'text-red-500 hover:text-red-600',
			bgClass: 'bg-transparent hover:bg-red-50',
			selectedBgClass: 'bg-red-50',
			iconColor: 'text-red-500',
			statusIndicator: <div className="h-2 w-2 rounded-full bg-red-500"></div>,
			label: 'Error'
		}
	};

	const config = statusConfig[walletStatus];

	const handleClick = async () => {
		setIsSelected(true);
		try {
			if (status === 'connected') {
				await open({ view: "Account" });
			} else {
				await connectWallet();
			}
		} finally {
			// 点击其他区域时自动取消选中状态
			document.addEventListener('click', (e) => {
				const target = e.target as HTMLElement;
				if (!target.closest('.wallet-indicator')) {
					setIsSelected(false);
				}
			}, { once: true });
		}
	};

	return (
		<div className="relative wallet-indicator">
			<TooltipIconButton
				tooltip={tooltipContent}
				variant="ghost"
				className={`
						inline-flex items-center justify-center gap-1.5
						h-8 px-3
						rounded-full
						transition-all duration-200
						${config.buttonClass}
						${isSelected ? config.selectedBgClass : config.bgClass}
						focus:outline-none
						focus:ring-2 
						focus:ring-green-500
						focus:ring-inset
						relative
						active:scale-95
					`}
				onClick={handleClick}
			>
				<div className="flex items-center justify-center gap-1.5">
					<Wallet
						size={16}
						className={`${isClient ? config.iconColor : statusConfig['disconnected'].iconColor} transition-transform ${isSelected ? 'scale-110' : ''}`}
					/>
				</div>
			</TooltipIconButton>
		</div>
	);
};