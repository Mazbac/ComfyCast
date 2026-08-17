# ComfyCast

ComfyCast adds Google Cast / Chromecast output nodes to ComfyUI so a finished image or video can be sent directly from a workflow to a TV or Cast-enabled display.

## What it does

- `Cast Image` accepts a native ComfyUI `IMAGE`.
- `Cast Video` accepts a native ComfyUI `VIDEO`.
- Discovers video-capable Google Cast devices on the local network.
- Adds a dynamic Cast-device picker to the nodes.
- Serves generated media from a private temporary LAN URL.
- Forces Google's Default Media Receiver so an unrelated active Cast session cannot create a false success.
- Verifies that the receiver loaded the exact ComfyCast media URL.
- Does **not** require ComfyUI to run with `--listen`.
- Does **not** upload media to a cloud service.

## Requirements

- ComfyUI with the V3 custom-node API and native `VIDEO` support.
- Python 3.11 or newer.
- The ComfyUI computer and Cast device must be reachable on the same LAN.
- Multicast/mDNS must be allowed for automatic discovery.

ComfyCast uses [PyChromecast](https://github.com/home-assistant-libs/pychromecast) for discovery and Cast protocol control.

## Installation

### ComfyUI Manager

Registry publishing is planned. Once ComfyCast is published to the ComfyUI Registry, install it through ComfyUI Manager and restart ComfyUI.

### Manual installation

Clone this repository into `ComfyUI/custom_nodes`:

```bash
git clone https://github.com/Mazbac/ComfyCast.git
```

Install the dependency in the same Python environment used by ComfyUI:

```bash
pip install -r ComfyCast/requirements.txt
```

For a Windows portable install, run the equivalent command with its embedded Python, for example:

```powershell
python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\ComfyCast\requirements.txt
```

Restart ComfyUI after installation.

## Usage

### Cast Image

Connect the final `IMAGE` output to **ComfyCast -> Cast Image**.

- **Cast device** - discovered TV/display.
- **image_index** - image to use when the input contains a batch.
- **title** - media title sent to the receiver.

The node converts the selected tensor to PNG, publishes it through ComfyCast's temporary local media server, and sends it to the selected display.

Casting intentionally takes over the selected Cast display by launching Google's Default Media Receiver.

### Cast Video

Connect a native ComfyUI `VIDEO` output to **ComfyCast -> Cast Video**.

- **Cast device** - discovered TV/display.
- **title** - media title sent to the receiver.
- **autoplay** - whether playback starts automatically.

Video is materialized through ComfyUI's native video API as MP4/H.264 for broad Cast compatibility.

## Network behavior

ComfyCast starts its own HTTP server only when media is actually cast. It listens on a random free port and advertises the computer's LAN IPv4 address to the receiver.

Each published file receives a high-entropy token in its URL. The server does not expose arbitrary filesystem paths or directory browsing. Media registrations expire automatically, while old temporary ComfyCast files are cleaned on later use.

If ComfyCast chooses the wrong network adapter, set the PC address explicitly before starting ComfyUI:

```text
COMFYCAST_HOST_IP=192.168.1.50
```

This setting is the **ComfyUI computer's** LAN address, not the Chromecast address.

## Known-host fallback

If multicast discovery is unavailable, provide one or more Cast-device IP addresses before starting ComfyUI:

```text
COMFYCAST_KNOWN_HOSTS=192.168.1.60,192.168.1.61
```

ComfyCast passes these addresses to PyChromecast as known hosts, and video-capable devices discovered from them appear in the normal Cast-device picker.

## Troubleshooting

**No devices appear**

- Confirm the Cast device and ComfyUI computer are on the same reachable network.
- Check guest Wi-Fi/client isolation, VLAN rules, VPNs, and multicast/mDNS filtering.
- Automatic discovery depends on mDNS (UDP 5353).
- Use **Refresh Cast devices** after changing the network.

**The receiver launches but media does not load**

- Confirm the receiver can reach the ComfyUI computer's LAN IP.
- Check the host firewall for blocked inbound Python connections on private networks.
- Set `COMFYCAST_HOST_IP` if the PC has multiple adapters and the wrong address was selected.

**Audio-only speakers are missing**

That is intentional. The current nodes only expose video-capable Cast targets because their inputs are images and videos.

## Architecture

```text
ComfyUI IMAGE / VIDEO
        |
        v
ComfyCast output node
        |
        +--> media materializer --> PNG / MP4 H.264
        |
        +--> tokenized LAN HTTP server
        |
        +--> PyChromecast --> Default Media Receiver
                              |
                              v
                         TV / display
```

Discovery and Cast calls run off ComfyUI's asyncio loop so network timeouts do not freeze the server UI.

## Development

Run the pure-Python tests with:

```bash
python -m unittest discover -s tests -v
```

The media-server test suite covers complete downloads, `HEAD`, and HTTP byte-range requests.

## License

MIT
