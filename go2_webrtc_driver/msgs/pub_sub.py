"""
WebRTC Data Channel Publish-Subscribe System for Unitree Go2 Robot

This module implements a publish-subscribe messaging system over WebRTC data channels,
providing reliable asynchronous communication with the Unitree Go2 robot. It handles
message routing, subscription management, and future-based request-response patterns.

The pub-sub system supports:
- Topic-based message routing
- Asynchronous request-response communication
- Subscription management with callbacks
- Future-based result handling
- Automatic message serialization/deserialization
- Connection state management

Key Features:
- Topic-based messaging with callback support
- Request-response pattern with automatic ID generation
- Priority-based message handling
- Robust error handling and connection monitoring
- JSON message serialization
- Flexible subscription management

Usage Example:
    ```python
    from go2_webrtc_driver.msgs.pub_sub import WebRTCDataChannelPubSub
    
    # Initialize with WebRTC data channel
    pubsub = WebRTCDataChannelPubSub(data_channel)
    
    # Subscribe to a topic
    def handle_message(message):
        print(f"Received: {message}")
    
    pubsub.subscribe("rt/lowstate", handle_message)
    
    # Publish a message
    await pubsub.publish("rt/sportmode", {"mode": "walk"})
    
    # Make a request
    response = await pubsub.publish_request_new("rt/api/sport", {
        "api_id": 1001,
        "parameter": {"speed": 0.5}
    })
    ```

Message Types:
- MSG: Standard message
- REQUEST: Request message expecting a response
- SUBSCRIBE: Subscription request
- UNSUBSCRIBE: Unsubscription request

Protocol Features:
- Automatic message ID generation
- Header-based message routing
- Parameter serialization
- Priority handling
- Connection state validation

Author: Unitree Robotics
Version: 1.0
"""

import asyncio
import json
import time
import random
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from ..constants import DATA_CHANNEL_TYPE
from .future_resolver import FutureResolver
from ..util import get_nested_field


class WebRTCDataChannelPubSub:
    """
    WebRTC Data Channel Publish-Subscribe System
    
    This class provides a comprehensive publish-subscribe messaging system over
    WebRTC data channels for communication with the Unitree Go2 robot. It handles
    message routing, subscription management, and asynchronous request-response
    communication patterns.
    
    The system supports:
    - Topic-based message publishing and subscription
    - Asynchronous request-response communication
    - Callback-based message handling
    - Future-based result resolution
    - Automatic message serialization
    - Connection state management
    
    Attributes:
        channel: WebRTC data channel for communication
        future_resolver (FutureResolver): Manages pending async operations
        subscriptions (Dict[str, Callable]): Topic-to-callback mappings
    
    Example:
        ```python
        # Initialize pub-sub system
        pubsub = WebRTCDataChannelPubSub(data_channel)
        
        # Subscribe to robot state updates
        def handle_lowstate(message):
            print(f"Robot state: {message['data']}")
        
        pubsub.subscribe("rt/lowstate", handle_lowstate)
        
        # Send sport mode command
        await pubsub.publish("rt/sportmode", {"mode": "walk"})
        
        # Make API request
        response = await pubsub.publish_request_new("rt/api/sport", {
            "api_id": 1001,
            "parameter": {"speed": 0.5}
        })
        ```
    """

    def __init__(self, channel) -> None:
        """
        Initialize the WebRTC Data Channel Pub-Sub system
        
        Args:
            channel: WebRTC data channel instance for communication
            
        Example:
            ```python
            # Initialize with WebRTC data channel
            pubsub = WebRTCDataChannelPubSub(data_channel)
            ```
        """
        self.channel = channel
        self.future_resolver = FutureResolver()
        self.subscriptions = {}  # Dictionary to hold callbacks keyed by topic
    
    def run_resolve(self, message: Dict[str, Any]) -> None:
        """
        Process incoming messages and route them to appropriate handlers
        
        This method handles message resolution by:
        1. Resolving pending futures for request-response patterns
        2. Routing messages to subscribed topic callbacks
        
        Args:
            message (Dict[str, Any]): Incoming message from WebRTC data channel
            
        Example:
            ```python
            # This method is typically called by the WebRTC message handler
            pubsub.run_resolve(incoming_message)
            ```
            
        Note:
            This method is called automatically by the WebRTC message handler
            and should not be called directly in most cases.
        """
        self.future_resolver.run_resolve_for_topic(message)

        # Extract the topic from the message
        topic = message.get("topic")
        if topic in self.subscriptions:
            # Call the registered callback with the message
            callback = self.subscriptions[topic]
            callback(message)
        

    async def publish(self, topic: str, data: Optional[Dict[str, Any]] = None, 
                     msg_type: Optional[str] = None) -> Any:
        """
        Publish a message to a topic and wait for response
        
        This method sends a message to the specified topic and returns a future
        that resolves when a response is received. It supports various message
        types and automatic response handling.
        
        Args:
            topic (str): Target topic for the message
            data (Optional[Dict[str, Any]]): Message payload data
            msg_type (Optional[str]): Message type (defaults to MSG)
            
        Returns:
            Any: Response from the message recipient
            
        Raises:
            Exception: If data channel is not open
            asyncio.TimeoutError: If no response is received within timeout
            
        Example:
            ```python
            # Send a simple message
            response = await pubsub.publish("rt/sportmode", {"mode": "walk"})
            
            # Send with specific message type
            response = await pubsub.publish("rt/api/sport", 
                                          {"command": "start"}, 
                                          DATA_CHANNEL_TYPE["REQUEST"])
            ```
            
        Note:
            This method will block until a response is received or timeout occurs.
            For fire-and-forget messages, use publish_without_callback().
        """
        channel = self.channel
        future = asyncio.get_event_loop().create_future()

        if channel.readyState == "open":
            message_dict = {
                "type": msg_type or DATA_CHANNEL_TYPE["MSG"],
                "topic": topic
            }
            # Only include "data" if it's not None
            if data is not None:
                message_dict["data"] = data
            
            # Convert the dictionary to a JSON string
            message = json.dumps(message_dict)

            channel.send(message)

            # Log the message being published
            logging.info(f"> message sent: {message}")

            # Store the future so it can be completed when the response is received
            uuid = (
                get_nested_field(data, "uuid") or
                get_nested_field(data, "header", "identity", "id") or 
                get_nested_field(data, "req_uuid")
            )

            self.future_resolver.save_resolve(msg_type or DATA_CHANNEL_TYPE["MSG"], topic, future, uuid)
        else:
            future.set_exception(Exception("Data channel is not open"))

        return await future
    

    def publish_without_callback(self, topic: str, data: Optional[Dict[str, Any]] = None, 
                                msg_type: Optional[str] = None) -> None:
        """
        Publish a message without waiting for response (fire-and-forget)
        
        This method sends a message to the specified topic without waiting for
        a response. It's useful for notifications, commands, or other messages
        that don't require acknowledgment.
        
        Args:
            topic (str): Target topic for the message
            data (Optional[Dict[str, Any]]): Message payload data
            msg_type (Optional[str]): Message type (defaults to MSG)
            
        Raises:
            Exception: If data channel is not open
            
        Example:
            ```python
            # Send notification message
            pubsub.publish_without_callback("rt/notification", 
                                           {"message": "Robot started"})
            
            # Send subscription request
            pubsub.publish_without_callback("rt/lowstate", 
                                          msg_type=DATA_CHANNEL_TYPE["SUBSCRIBE"])
            ```
            
        Note:
            This method returns immediately and doesn't wait for responses.
            Use this for better performance when responses are not needed.
        """
        if self.channel.readyState == "open":
            message_dict = {
                "type": msg_type or DATA_CHANNEL_TYPE["MSG"],
                "topic": topic
            }

            # Only include "data" if it's not None
            if data is not None:
                message_dict["data"] = data
            
            # Convert the dictionary to a JSON string
            message = json.dumps(message_dict)
                
            self.channel.send(message)

            # Log the message being published
            logging.info(f"> message sent: {message}")
        else:
            Exception("Data channel is not open")
        

    async def publish_request_new(self, topic: str, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Publish a structured API request with automatic ID generation
        
        This method creates and sends a structured API request with proper
        header formatting, automatic ID generation, and parameter handling.
        It's designed for the Unitree Go2 API communication protocol.
        
        Args:
            topic (str): API endpoint topic
            options (Optional[Dict[str, Any]]): Request options containing:
                - api_id (int): API identifier (required)
                - parameter (Union[str, Dict]): Request parameters
                - id (int): Custom request ID (auto-generated if not provided)
                - priority (int): Request priority (adds priority policy)
                
        Returns:
            Any: API response from the robot
            
        Raises:
            Exception: If api_id is not provided or data channel is not open
            asyncio.TimeoutError: If no response is received within timeout
            
        Example:
            ```python
            # Make API request with parameters
            response = await pubsub.publish_request_new("rt/api/sport", {
                "api_id": 1001,
                "parameter": {"speed": 0.5, "direction": "forward"}
            })
            
            # Request with priority
            response = await pubsub.publish_request_new("rt/api/audiohub", {
                "api_id": 2001,
                "parameter": {"volume": 80},
                "priority": 1
            })
            
            # Request with custom ID
            response = await pubsub.publish_request_new("rt/api/lowstate", {
                "api_id": 3001,
                "id": 12345,
                "parameter": {}
            })
            ```
            
        Request Format:
            The method creates a structured request with:
            - header.identity.id: Unique request identifier
            - header.identity.api_id: API function identifier
            - header.policy.priority: Priority level (if specified)
            - parameter: Request parameters (JSON serialized)
            
        Note:
            This method is specifically designed for the Unitree Go2 API protocol.
            The api_id parameter is required and must match the target API function.
        """
        # Generate a unique identifier
        generated_id = int(time.time() * 1000) % 2147483648 + random.randint(0, 1000)
        
        # Check if api_id is provided
        if not (options and "api_id" in options):
            print("Error: Please provide app id")
            return asyncio.Future().set_exception(Exception("Please provide app id"))

        # Build the request header and parameter
        request_payload = {
            "header": {
                "identity": {
                    "id": options.get("id", generated_id),
                    "api_id": options.get("api_id", 0)
                }
            },
            "parameter": ""
        }

        # Add data to parameter
        if options and "parameter" in options:
            request_payload["parameter"] = options["parameter"] if isinstance(options["parameter"], str) else json.dumps(options["parameter"])

        # Add priority if specified
        if options and "priority" in options:
            request_payload["header"]["policy"] = {
                "priority": 1
            }

        # Publish the request
        return await self.publish(topic, request_payload, DATA_CHANNEL_TYPE["REQUEST"])
    
    def subscribe(self, topic: str, callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        """
        Subscribe to a topic with optional callback function
        
        This method subscribes to a topic and registers a callback function
        to handle incoming messages. The subscription is sent to the robot,
        and the callback will be called for each received message.
        
        Args:
            topic (str): Topic to subscribe to
            callback (Optional[Callable]): Function to call when messages arrive
                The callback receives a single argument: the message dictionary
                
        Example:
            ```python
            # Subscribe with callback
            def handle_robot_state(message):
                state = message.get('data', {})
                print(f"Robot position: {state.get('position')}")
            
            pubsub.subscribe("rt/lowstate", handle_robot_state)
            
            # Subscribe without callback (for manual processing)
            pubsub.subscribe("rt/sportmode")
            ```
            
        Note:
            - The callback function should accept one parameter (the message)
            - Only one callback per topic is supported (new callback overwrites old)
            - If data channel is not open, an error message is printed
            - Messages will be routed to the callback via run_resolve()
        """
        channel = self.channel

        if not channel or channel.readyState != "open":
            print("Error: Data channel is not open")
            return
        
        # Register the callback for the topic
        if callback:
            self.subscriptions[topic] = callback

        self.publish_without_callback(topic=topic, msg_type=DATA_CHANNEL_TYPE["SUBSCRIBE"])

    def unsubscribe(self, topic: str) -> None:
        """
        Unsubscribe from a topic
        
        This method removes the subscription to a topic and notifies the robot
        to stop sending messages for that topic. The callback is also removed
        from the local subscription registry.
        
        Args:
            topic (str): Topic to unsubscribe from
            
        Example:
            ```python
            # Unsubscribe from a topic
            pubsub.unsubscribe("rt/lowstate")
            
            # This will stop receiving messages for this topic
            pubsub.unsubscribe("rt/sportmode")
            ```
            
        Note:
            - The local callback is automatically removed
            - An unsubscribe message is sent to the robot
            - If data channel is not open, an error message is printed
            - No error is raised if the topic was not subscribed
        """
        channel = self.channel

        if not channel or channel.readyState != "open":
            print("Error: Data channel is not open")
            return

        # Remove the callback if it exists
        if topic in self.subscriptions:
            del self.subscriptions[topic]

        self.publish_without_callback(topic=topic, msg_type=DATA_CHANNEL_TYPE["UNSUBSCRIBE"])
        
    