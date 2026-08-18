import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_NAMES = new Set(["ComfyCastImage", "ComfyCastVideo"]);

async function fetchDevices(force = false) {
    const suffix = force ? "?refresh=1" : "";
    const response = await api.fetchApi(`/comfycast/devices${suffix}`, {
        cache: "no-store",
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Device discovery failed (${response.status})`);
    }
    return payload.devices || [];
}

async function sendControl(device, action) {
    const response = await api.fetchApi("/comfycast/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device, action }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
        throw new Error(payload.error || `Cast control failed (${response.status})`);
    }
    return payload;
}

function describeDevice(device) {
    if (device.label) return device.label;
    const model = device.model ? ` - ${device.model}` : "";
    return `${device.name}${model} - ${device.host}`;
}

function installDevicePicker(node) {
    const deviceWidget = node.widgets?.find((widget) => widget.name === "device");
    if (!deviceWidget || deviceWidget._comfycastInstalled) return;
    deviceWidget._comfycastInstalled = true;

    deviceWidget.type = "combo";
    deviceWidget.label = "Cast device";
    deviceWidget.options = {
        ...(deviceWidget.options || {}),
        values: [],
    };

    const status = node.addWidget(
        "text",
        "Cast status",
        "Discovering devices...",
        () => {},
        {},
    );
    status.serialize = false;
    status.disabled = true;

    let controlsBusy = false;
    const runControl = async (action) => {
        const device = String(deviceWidget.value || "").trim();
        if (!device) {
            status.value = "Select a Cast device first";
            return;
        }
        if (controlsBusy) return;
        controlsBusy = true;
        status.value = `${action}...`;
        node.setDirtyCanvas?.(true, true);
        try {
            const result = await sendControl(device, action);
            const state = result.player_state || action;
            status.value = `${result.name || "Cast"}: ${state}`;
        } catch (error) {
            status.value = `Control error: ${error.message || error}`;
        } finally {
            controlsBusy = false;
            node.setDirtyCanvas?.(true, true);
        }
    };

    for (const [label, action] of [
        ["Start / Resume", "start"],
        ["Pause", "pause"],
        ["Stop", "stop"],
        ["End Cast", "end"],
    ]) {
        const control = node.addWidget("button", label, null, () => runControl(action), {});
        control.serialize = false;
    }

    const refresh = async (force = false) => {
        status.value = force ? "Refreshing devices..." : "Discovering devices...";
        try {
            const devices = await fetchDevices(force);
            const choices = devices.map(describeDevice);
            deviceWidget.options = {
                ...(deviceWidget.options || {}),
                values: choices,
            };

            const current = String(deviceWidget.value || "").toLowerCase();
            const match = devices.find((device) =>
                [device.uuid, device.name, device.host, describeDevice(device)].some(
                    (value) => String(value).toLowerCase() === current,
                ),
            );
            deviceWidget.value = match ? describeDevice(match) : choices[0] || "";
            status.value = devices.length
                ? `${devices.length} display${devices.length === 1 ? "" : "s"} found`
                : "No video-capable Cast devices found";
        } catch (error) {
            deviceWidget.options = {
                ...(deviceWidget.options || {}),
                values: [],
            };
            status.value = `Discovery error: ${error.message || error}`;
        }
        node.setDirtyCanvas?.(true, true);
    };

    const refreshButton = node.addWidget(
        "button",
        "Refresh Cast devices",
        null,
        () => refresh(true),
        {},
    );
    refreshButton.serialize = false;
    refresh(false);
}

app.registerExtension({
    name: "ComfyCast.DevicePicker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!NODE_NAMES.has(nodeData.name)) return;
        const original = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = original?.apply(this, args);
            installDevicePicker(this);
            return result;
        };
    },
});
