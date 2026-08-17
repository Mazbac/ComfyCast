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

function describeDevice(device) {
    const model = device.model ? ` — ${device.model}` : "";
    return `${device.name}${model} — ${device.host}`;
}

function installDevicePicker(node) {
    const deviceWidget = node.widgets?.find((widget) => widget.name === "device");
    if (!deviceWidget || deviceWidget._comfycastInstalled) return;
    deviceWidget._comfycastInstalled = true;

    const labels = new Map();
    const labelFor = (value) => labels.get(value) || value || "";

    deviceWidget.type = "combo";
    deviceWidget.label = "Cast device";
    deviceWidget.options = {
        ...(deviceWidget.options || {}),
        values: [],
        getOptionLabel: labelFor,
    };

    const status = node.addWidget(
        "text",
        "Cast status",
        "Discovering devices…",
        () => {},
        {},
    );
    status.serialize = false;
    status.disabled = true;

    const refresh = async (force = false) => {
        status.value = force ? "Refreshing devices…" : "Discovering devices…";
        try {
            const devices = await fetchDevices(force);
            labels.clear();
            const ids = devices.map((device) => {
                labels.set(device.uuid, describeDevice(device));
                return device.uuid;
            });

            deviceWidget.options = {
                ...(deviceWidget.options || {}),
                values: ids,
                getOptionLabel: labelFor,
            };

            const current = String(deviceWidget.value || "").toLowerCase();
            const match = devices.find((device) =>
                [device.uuid, device.name, device.host].some(
                    (value) => String(value).toLowerCase() === current,
                ),
            );
            deviceWidget.value = match?.uuid || ids[0] || "";
            status.value = devices.length
                ? `${devices.length} display${devices.length === 1 ? "" : "s"} found`
                : "No video-capable Cast devices found";
        } catch (error) {
            deviceWidget.options = {
                ...(deviceWidget.options || {}),
                values: [],
                getOptionLabel: labelFor,
            };
            status.value = `Discovery error: ${error.message || error}`;
        }
        node.setDirtyCanvas?.(true, true);
    };

    const button = node.addWidget(
        "button",
        "Refresh Cast devices",
        null,
        () => refresh(true),
        {},
    );
    button.serialize = false;
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
