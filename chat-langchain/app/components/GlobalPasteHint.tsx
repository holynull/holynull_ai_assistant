// GlobalPasteHint.tsx
"use client";

import React, { useState, useEffect } from 'react';
import { Box, Flex, Text, IconButton, Icon } from '@chakra-ui/react';
import { CloseIcon } from '@chakra-ui/icons';
import { FaLightbulb } from 'react-icons/fa';

interface GlobalPasteHintProps {
  onClose?: () => void;
  autoHideDelay?: number; // in milliseconds, default 8000
  message?: string;
}

export const GlobalPasteHint: React.FC<GlobalPasteHintProps> = ({
  onClose,
  autoHideDelay = 8000,
  message = 'You can paste images from clipboard at any time (Ctrl/Cmd + V)'
}) => {
  const [isPaused, setIsPaused] = useState(false);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!isPaused) {
        setIsVisible(false);
        onClose?.();
      }
    }, autoHideDelay);

    return () => clearTimeout(timer);
  }, [isPaused, autoHideDelay, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    onClose?.();
  };

  if (!isVisible) return null;

  return (
    <Box
      position="fixed"
      top={0}
      left={0}
      right={0}
      bg="rgba(0, 0, 0, 0.9)"
      color="white"
      py={2}
      zIndex={1000}
      backdropFilter="blur(8px)"
      borderBottom="1px solid rgba(255, 255, 255, 0.1)"
      transition="all 0.3s ease"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => {
        setIsPaused(false);
        const timer = setTimeout(() => {
          setIsVisible(false);
          onClose?.();
        }, 3000);
        return () => clearTimeout(timer);
      }}
    >
      <Flex
        maxW="container.xl"
        mx="auto"
        px={4}
        justify="center"
        align="center"
        gap={2}
      >
        <Icon as={FaLightbulb} color="yellow.400" />
        <Text fontSize="sm" fontWeight="medium">
          {message}
        </Text>
        {!isPaused && (
          <Box
            position="absolute"
            bottom={0}
            left={0}
            height="2px"
            bg="blue.400"
            animation="progressBar 8s linear"
            sx={{
              '@keyframes progressBar': {
                '0%': { width: '100%' },
                '100%': { width: '0%' },
              },
            }}
          />
        )}
        <IconButton
          aria-label="Close hint"
          icon={<CloseIcon />}
          size="xs"
          variant="ghost"
          colorScheme="whiteAlpha"
          onClick={handleClose}
          ml={2}
          _hover={{
            bg: 'whiteAlpha.200'
          }}
        />
      </Flex>
    </Box>
  );
};

export default GlobalPasteHint;