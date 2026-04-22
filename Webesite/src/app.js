let device;
let characteristic;

const SERVICE_UUID = "12345678-1234-1234-1234-123456789abc";
const CHARACTERISTIC_UUID = "abcd1234-5678-1234-5678-abcdef123456";

const statusLbl = document.getElementById("status");
const connectBtn = document.getElementById("bleConnectBtn");

const lockBtn = document.getElementById("lockBtn");
const unlockBtn = document.getElementById("unlockBtn");

const lockLbl = document.getElementById("lockLbl");

const textbox = document.getElementById("txtBox");

if (!navigator.bluetooth) {
    alert("Bluetooth is not supported on this device/browser. Please use Chrome on Android or a desktop browser.");
}

/* debounce flag */

let buttonCooldown = false;

/* helper function */

function startCooldown() {

    lockLbl.textContent = "Locking Mode: Processing...";
    buttonCooldown = true;

    lockBtn.disabled = true;
    unlockBtn.disabled = true;

    setTimeout(() => {

        buttonCooldown = false;

        lockBtn.disabled = false;
        unlockBtn.disabled = false;

    }, 2000);
}


/* CONNECT BUTTON */

connectBtn.addEventListener("click", async () => {

    try {

        statusLbl.textContent = "Status: Connecting...";
        statusLbl.className = "status connecting";

        device = await navigator.bluetooth.requestDevice({
            filters: [{ name: "ZipGuard" }],
            optionalServices: [SERVICE_UUID]
        });

        const server = await device.gatt.connect();

        const service = await server.getPrimaryService(SERVICE_UUID);

        characteristic = await service.getCharacteristic(CHARACTERISTIC_UUID);

        await characteristic.startNotifications();

        characteristic.addEventListener(
            "characteristicvaluechanged",
            event => {
                let value = new TextDecoder().decode(
                    event.target.value
                );

                console.log("GPS received:", value);

                let coords = value.split(",");

                let lat = parseFloat(coords[0]);
                let lng = parseFloat(coords[1]);

                updateLocation(lat, lng);
            }
        );

        statusLbl.textContent = "Status: Connected";
        statusLbl.className = "status connected";

        lockBtn.disabled = false;
        unlockBtn.disabled = false;

        // Disconnect listener

        device.addEventListener("gattserverdisconnected", () => {

            statusLbl.textContent = "Status: Disconnected";
            statusLbl.className = "status disconnected";

            lockBtn.disabled = true;
            unlockBtn.disabled = true;

            console.log("BLE lost connection.");

        });

    } catch (error) {

        console.log(error);

        statusLbl.textContent = "Status: Disconnected";
        statusLbl.className = "status disconnected";

    }

});


/* LOCK BUTTON */

lockBtn.addEventListener("click", async () => {

    if (!characteristic || buttonCooldown) return;

    if (textbox.value != "67") return;

    await characteristic.writeValue(
        new TextEncoder().encode("0")
    );

    startCooldown();

    lockLbl.textContent = "Locking Mode: ENABLED";
});


/* UNLOCK BUTTON */

unlockBtn.addEventListener("click", async () => {

    if (!characteristic || buttonCooldown) return;

    if (textbox.value != "67") return;

    await characteristic.writeValue(
        new TextEncoder().encode("1")
    );

    startCooldown();

    lockLbl.textContent = "Locking Mode: DISABLED";
});
