"""Unified audio streaming module for AirPlay and DLNA devices."""

import asyncio
from pathlib import Path
from typing import Optional

from rich.console import Console

from .discover import DiscoveredDevice

console = Console()


async def stream_to_device(
    device: DiscoveredDevice,
    audio_file: Path,
    wait_for_completion: bool = True,
) -> None:
    """Stream an audio file to a device (AirPlay or DLNA).

    Args:
        device: Discovered device (AirPlay or DLNA)
        audio_file: Path to audio file to stream
        wait_for_completion: Whether to wait for playback to complete

    Raises:
        Exception: If connection or streaming fails
    """
    if device.device_type == "AirPlay":
        await _stream_to_airplay(device.raw_device, audio_file, wait_for_completion)
    elif device.device_type == "DLNA":
        from .dlna_player import stream_to_dlna_device
        await stream_to_dlna_device(device.raw_device, audio_file, wait_for_completion)
    else:
        raise ValueError(f"Unknown device type: {device.device_type}")


async def _stream_to_airplay(
    device_config,
    audio_file: Path,
    wait_for_completion: bool = True,
) -> None:
    """Stream an audio file to an AirPlay device."""
    import pyatv

    loop = asyncio.get_event_loop()
    audio_path = str(audio_file)

    console.print(f"[dim]Connecting to AirPlay device...[/dim]")

    atv = await pyatv.connect(device_config, loop)

    try:
        console.print(f"[dim]Streaming: {audio_file.name}[/dim]")
        await atv.stream.stream_file(audio_path)

        if wait_for_completion:
            await asyncio.sleep(1)
            console.print("[dim]Waiting for playback to complete...[/dim]")
            await asyncio.sleep(2)

        console.print("[green]Playback completed[/green]")

    finally:
        atv.close()
        console.print("[dim]Disconnected[/dim]")


async def play_url(
    device: DiscoveredDevice,
    url: str,
    position: int = 0,
) -> None:
    """Play a URL on a device.

    Args:
        device: Discovered device
        url: URL to play
        position: Starting position in seconds

    Raises:
        Exception: If playback fails
    """
    if device.device_type == "AirPlay":
        import pyatv

        loop = asyncio.get_event_loop()
        console.print(f"[dim]Connecting to AirPlay device...[/dim]")
        atv = await pyatv.connect(device.raw_device, loop)

        try:
            console.print(f"[dim]Playing URL: {url}[/dim]")
            await atv.stream.play_url(url, position=position)
            console.print("[green]Playback completed[/green]")
        finally:
            atv.close()
            console.print("[dim]Disconnected[/dim]")

    elif device.device_type == "DLNA":
        from .dlna_player import AVTRANSPORT_SERVICE_TYPE
        from async_upnp_client.aiohttp import AiohttpRequester
        from async_upnp_client.client_factory import UpnpFactory

        console.print(f"[dim]Connecting to DLNA device...[/dim]")
        requester = AiohttpRequester()
        factory = UpnpFactory(requester)
        upnp_device = await factory.async_create_device(device.raw_device.location)

        av_transport = upnp_device.find_service(service_type=AVTRANSPORT_SERVICE_TYPE)
        if not av_transport:
            raise Exception("AVTransport service not found")

        try:
            await av_transport.action("Stop").async_call(InstanceID=0)
        except:
            pass

        await av_transport.action("SetAVTransportURI").async_call(
            InstanceID=0,
            CurrentURI=url,
            CurrentURIMetaData="",
        )
        await av_transport.action("Play").async_call(InstanceID=0, Speed="1")
        console.print("[green]Playback started[/green]")


async def quick_play(
    device_name: str,
    text: str,
    voice: Optional[str] = None,
) -> None:
    """Quick play text on a device (combine TTS + stream).

    Args:
        device_name: Name of the device
        text: Text to speak
        voice: Optional voice to use

    Raises:
        Exception: If device not found or playback fails
    """
    from .discover import find_device_by_name
    # Find device
    device = await find_device_by_name(device_name)
    if not device:
        raise ValueError(f"Device '{device_name}' not found")

    console.print(f"[green]Found device: {device.name} ({device.device_type})[/green]")

    # Generate speech
    audio_file = await generate_speech(text, voice=voice)

    try:
        # Stream to device
        await stream_to_device(device, audio_file)
    finally:
        # Cleanup temp file
        if audio_file.exists():
            audio_file.unlink()
