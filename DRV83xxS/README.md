This is High Level Analyzer for Saleae Logic 2.  It decodes for the Texas Instruments DRV8323S/DRV8323RS gate-driver protocol.

Each 16-bit SPI transaction is displayed as:
```text
READ | DRIVER_CONTROL | 0x2 | 0x0A0 | DIS_CPUV=0 (fault enabled), ... PWM_MODE=1 (3x PWM), ...
WRITE | GATE_DRIVE_HS | 0x3 | 0x377 | LOCK=3 (unlock), IDRIVEP_HS=7 (190 mA source), ...
```

The data table also contains separate operation, register, address, value,
bitfields, MOSI, and MISO columns.

# Logic 2 setup

1. Add a standard **SPI** analyzer.
2. Assign `SDI` to MOSI, `SDO` to MISO, and the selected driver's `nSCS` to Enable (optional)
3. Configure CPOL 0, CPHA 1 (data valid on the falling edge), MSB first, and active-low Enable
4. Use 16 bits per transfer. Eight bits per transfer is also supported when `nSCS` is configured; the HLA joins each pair of bytes.
5. Add this **DRV8323S** High Level Analyzer on top of the SPI analyzer.

![TI SPI Settings](TI-SPI-settings.png)

# Screenshot
![Screenshot](DRV8323S.png)