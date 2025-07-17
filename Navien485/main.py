#!/usr/bin/env python3
"""
Navien RS485 to MQTT Bridge
Refactored version with proper separation of concerns.
"""

from config_manager import ConfigManager
from wallpad import Wallpad
from device_registry import DeviceRegistry
from logger import setup_logger


def main():
    """Main entry point for the Navien RS485 MQTT bridge."""
    logger = setup_logger("main")
    
    # Load configuration
    config = ConfigManager()
    
    # Validate configuration before proceeding
    if not config.validate_config():
        return 1
    
    # Print configuration for debugging
    config.print_config()
    
    # Initialize wallpad controller
    wallpad = Wallpad(config)
    
    # Register all devices
    registry = DeviceRegistry(wallpad)
    registry.register_all_devices()
    logger.info(f"Registered {len(wallpad._device_list)} devices")
    
    # Start listening for messages
    logger.info("Starting MQTT Bridge...")
    try:
        wallpad.listen()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())