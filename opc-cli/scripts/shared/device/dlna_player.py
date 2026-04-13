"""DLNA audio streaming module."""

import asyncio
import os
import socket
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import UpnpDevice
from async_upnp_client.client_factory import UpnpFactory
from rich.console import Console

console = Console()

# DLNA service type for AVTransport
AVTRANSPORT_SERVICE_TYPE = "urn:schemas-upnp-org:service:AVTransport:1"


class QuietHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Quiet HTTP request handler that doesn't log requests."""

    def __init__(self, *args, directory=None, **kwargs):
        self.directory = directory
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        pass


class DLNADevice:
    """Wrapper for DLNA MediaRenderer device."""

    def __init__(self, device: UpnpDevice, location: str):
        self.device = device
        self.location = location
        self.name = device.name or device.friendly_name or "Unknown DLNA Device"
        self.model_name = device.model_name or "Unknown"
        self.udn = device.udn or ""

    def __repr__(self):
        return f"DLNADevice(name='{self.name}', model='{self.model_name}')"


def get_local_ip() -> str:
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def start_http_server(directory: str, port: int = 0) -> tuple[int, HTTPServer]:
    """Start a simple HTTP server in a thread.

    Args:
        directory: Directory to serve files from
        port: Port to listen on (0 for auto-assign)

    Returns:
        Tuple of (port, server)
    """
    # Create a handler class bound to the specific directory
    handler = lambda *args, **kwargs: QuietHTTPRequestHandler(*args, directory=directory, **kwargs)
    server = HTTPServer(("0.0.0.0", port), handler)
    actual_port = server.server_address[1]

    def serve():
        server.serve_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    return actual_port, server


async def discover_dlna_devices(timeout: int = 5) -> list[DLNADevice]:
    """Discover DLNA MediaRenderer devices on the network.

    Args:
        timeout: Scan timeout in seconds

    Returns:
        List of DLNA MediaRenderer devices
    """
    from async_upnp_client.search import async_search
    from async_upnp_client.ssdp import SSDP_ST_ALL

    devices_found = {}

    async def on_response(response):
        """Handle SSDP response."""
        st = response.get("ST", "")
        location = response.get("LOCATION", "")
        usn = response.get("USN", "")

        # Only care about MediaRenderer devices
        if "MediaRenderer" not in st or not location:
            return

        # Avoid duplicates
        if usn in devices_found:
            return

        try:
            # Connect to device and get info
            requester = AiohttpRequester()
            factory = UpnpFactory(requester)
            device = await factory.async_create_device(location)

            # Verify it has AVTransport service
            if device.find_service(service_type=AVTRANSPORT_SERVICE_TYPE):
                dlna_device = DLNADevice(device, location)
                devices_found[usn] = dlna_device
                console.print(f"[dim]Found DLNA device: {dlna_device.name}[/dim]")

        except Exception as e:
            console.print(f"[dim]Failed to connect to {location}: {e}[/dim]")

    await async_search(
        async_callback=on_response,
        timeout=timeout,
        search_target=SSDP_ST_ALL,
    )

    return list(devices_found.values())


async def stream_to_dlna_device(
    device: DLNADevice,
    audio_file: Path,
    wait_for_completion: bool = True,
) -> None:
    """Stream an audio file to a DLNA device.

    Args:
        device: DLNA device wrapper
        audio_file: Path to audio file
        wait_for_completion: Whether to wait for playback to complete

    Raises:
        Exception: If playback fails
    """
    # Start HTTP server to serve the audio file
    temp_dir = str(audio_file.parent)
    filename = audio_file.name

    port, server = start_http_server(temp_dir, port=0)

    local_ip = get_local_ip()
    audio_url = f"http://{local_ip}:{port}/{filename}"

    console.print(f"[dim]Streaming from: {audio_url}[/dim]")

    # Wait for HTTP server to be ready
    await asyncio.sleep(0.5)

    # Reconnect to device (original connection may have closed)
    requester = AiohttpRequester()
    factory = UpnpFactory(requester)
    upnp_device = await factory.async_create_device(device.location)

    av_transport = upnp_device.find_service(service_type=AVTRANSPORT_SERVICE_TYPE)
    if not av_transport:
        server.shutdown()
        raise Exception("AVTransport service not found")

    try:

        # Stop any current playback
        try:
            await av_transport.action("Stop").async_call(InstanceID=0)
        except:
            pass

        # Set URI and play
        console.print(f"[dim]Setting playback URI...[/dim]")
        await av_transport.action("SetAVTransportURI").async_call(
            InstanceID=0,
            CurrentURI=audio_url,
            CurrentURIMetaData="",
        )

        console.print(f"[dim]Starting playback...[/dim]")
        await av_transport.action("Play").async_call(InstanceID=0, Speed="1")

        console.print("[green]Playback started[/green]")

        if wait_for_completion:
            # Monitor playback status
            await asyncio.sleep(1)
            play_time = 0
            max_wait = 300  # 5 minutes max

            while play_time < max_wait:
                await asyncio.sleep(2)
                play_time += 2

                try:
                    info = await av_transport.action("GetTransportInfo").async_call(
                        InstanceID=0
                    )
                    state = info.get("CurrentTransportState", "UNKNOWN")

                    if state == "STOPPED":
                        console.print("[green]Playback completed[/green]")
                        break
                    elif state == "PLAYING":
                        continue
                    elif state == "PAUSED_PLAYBACK":
                        continue

                except Exception as e:
                    console.print(f"[dim]Could not get status: {e}[/dim]")
                    break

    finally:
        server.shutdown()
        console.print("[dim]HTTP server stopped[/dim]")


async def quick_play_dlna(
    device_name: str,
    text: str,
    voice: Optional[str] = None,
) -> None:
    """Quick play text on a DLNA device.

    Args:
        device_name: Name of the DLNA device
        text: Text to speak
        voice: Optional voice to use

    Raises:
        Exception: If device not found or playback fails
    """
    from say_lib.tts import generate_speech

    # Find device
    console.print(f"[dim]Searching for DLNA device: {device_name}...[/dim]")
    devices = await discover_dlna_devices(timeout=5)

    device = None
    name_lower = device_name.lower()
    for d in devices:
        if d.name.lower() == name_lower:
            device = d
            break
        if name_lower in d.name.lower():
            device = d

    if not device:
        raise ValueError(f"DLNA device '{device_name}' not found")

    console.print(f"[green]Found DLNA device: {device.name}[/green]")

    # Generate speech
    audio_file = await generate_speech(text, voice=voice)

    try:
        # Stream to device
        await stream_to_dlna_device(device, audio_file)
    finally:
        # Cleanup temp file
        if audio_file.exists():
            audio_file.unlink()
