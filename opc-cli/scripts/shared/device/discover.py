"""Device discovery for AirPlay/HomePod and DLNA devices."""

import asyncio
from dataclasses import dataclass
from typing import List, Optional

import pyatv
from pyatv.const import Protocol
from pyatv.interface import BaseConfig
from rich.console import Console

console = Console()


@dataclass
class DiscoveredDevice:
    """Unified device representation."""

    name: str
    device_type: str  # "AirPlay" or "DLNA"
    model: str
    address: str
    raw_device: object  # BaseConfig for AirPlay, DLNADevice for DLNA


async def discover_airplay_devices(
    timeout: int = 5,
    hosts: Optional[List[str]] = None,
) -> List[DiscoveredDevice]:
    """Discover AirPlay devices on the network.

    Args:
        timeout: Scan timeout in seconds
        hosts: Optional list of specific hosts to scan

    Returns:
        List of discovered AirPlay devices
    """
    loop = asyncio.get_event_loop()

    console.print(f"[dim]Scanning for AirPlay devices (timeout: {timeout}s)...[/dim]")

    if hosts:
        devices = await pyatv.scan(loop, hosts=hosts, timeout=timeout)
    else:
        devices = await pyatv.scan(loop, timeout=timeout)

    # Filter to AirPlay-capable devices
    airplay_devices = filter_airplay_devices(devices)

    # Convert to unified format
    result = []
    for device in airplay_devices:
        model_name = "Unknown"
        if device.device_info.model:
            model_name = device.device_info.model.name

        result.append(
            DiscoveredDevice(
                name=device.name or "Unknown",
                device_type="AirPlay",
                model=model_name,
                address=str(device.address),
                raw_device=device,
            )
        )

    return result


def filter_airplay_devices(devices: List[BaseConfig]) -> List[BaseConfig]:
    """Filter devices to only include those with AirPlay/RAOP support.

    Args:
        devices: List of discovered devices

    Returns:
        Filtered list of AirPlay-capable devices
    """
    airplay_devices = []
    for device in devices:
        # Check if device has AirPlay or RAOP service
        has_airplay = device.get_service(Protocol.AirPlay) is not None
        has_raop = device.get_service(Protocol.RAOP) is not None

        if has_airplay or has_raop:
            airplay_devices.append(device)

    return airplay_devices


async def discover_dlna_devices(timeout: int = 5) -> List[DiscoveredDevice]:
    """Discover DLNA MediaRenderer devices on the network.

    Args:
        timeout: Scan timeout in seconds

    Returns:
        List of discovered DLNA devices
    """
    from .dlna_player import discover_dlna_devices as _discover_dlna

    console.print(f"[dim]Scanning for DLNA devices (timeout: {timeout}s)...[/dim]")

    dlna_devices = await _discover_dlna(timeout=timeout)

    # Convert to unified format
    result = []
    for device in dlna_devices:
        # Extract IP from location
        ip = "Unknown"
        try:
            from urllib.parse import urlparse

            parsed = urlparse(device.location)
            ip = parsed.hostname or "Unknown"
        except:
            pass

        result.append(
            DiscoveredDevice(
                name=device.name,
                device_type="DLNA",
                model=device.model_name,
                address=ip,
                raw_device=device,
            )
        )

    return result


async def discover_all_devices(
    timeout: int = 5,
    include_airplay: bool = True,
    include_dlna: bool = True,
) -> List[DiscoveredDevice]:
    """Discover all supported devices (AirPlay and DLNA).

    Args:
        timeout: Scan timeout in seconds
        include_airplay: Whether to scan for AirPlay devices
        include_dlna: Whether to scan for DLNA devices

    Returns:
        List of all discovered devices
    """
    devices = []

    if include_airplay:
        airplay_devices = await discover_airplay_devices(timeout=timeout)
        devices.extend(airplay_devices)

    if include_dlna:
        dlna_devices = await discover_dlna_devices(timeout=timeout)
        devices.extend(dlna_devices)

    return devices


async def find_device_by_name(
    name: str,
    timeout: int = 5,
    prefer_type: Optional[str] = None,
) -> Optional[DiscoveredDevice]:
    """Find a specific device by name.

    Args:
        name: Device name to search for (case-insensitive)
        timeout: Scan timeout in seconds
        prefer_type: Prefer "AirPlay" or "DLNA" if both match

    Returns:
        Device if found, None otherwise
    """
    devices = await discover_all_devices(timeout=timeout)
    name_lower = name.lower()

    matches = []
    for device in devices:
        if device.name.lower() == name_lower:
            matches.append(device)
        elif name_lower in device.name.lower():
            matches.append(device)

    if not matches:
        return None

    # If multiple matches, prefer the specified type
    if len(matches) > 1 and prefer_type:
        for match in matches:
            if match.device_type == prefer_type:
                return match

    return matches[0]


def print_device_list(devices: List[DiscoveredDevice]) -> None:
    """Print a formatted list of devices.

    Args:
        devices: List of devices to display
    """
    if not devices:
        console.print("[yellow]No devices found.[/yellow]")
        return

    # Group by type
    airplay_devices = [d for d in devices if d.device_type == "AirPlay"]
    dlna_devices = [d for d in devices if d.device_type == "DLNA"]

    console.print(f"\n[bold green]Found {len(devices)} device(s):[/bold green]\n")

    if airplay_devices:
        console.print("[bold cyan]AirPlay Devices:[/bold cyan]\n")
        for i, device in enumerate(airplay_devices, 1):
            console.print(f"  [bold]{i}.[/bold] {device.name}")
            console.print(f"     Address: {device.address}")
            console.print(f"     Model: {device.model}")
            console.print()

    if dlna_devices:
        console.print("[bold cyan]DLNA Devices:[/bold cyan]\n")
        for i, device in enumerate(dlna_devices, 1):
            console.print(f"  [bold]{i}.[/bold] {device.name}")
            console.print(f"     Address: {device.address}")
            console.print(f"     Model: {device.model}")
            console.print()
