"""
Saleae High Level Analyzer for the TI's DRV8323S SPI protocol
"""

from saleae.analyzers import AnalyzerFrame, HighLevelAnalyzer


SOURCE_CURRENT_MA = (10, 30, 60, 80, 120, 140, 170, 190, 260, 330, 370, 440, 570, 680, 820, 1000)

SINK_CURRENT_MA = (20, 60, 120, 160, 240, 280, 340, 380, 520, 660, 740, 880, 1140, 1360, 1640, 2000)

VDS_LEVEL_V = (
    "0.06", "0.13", "0.20", "0.26",
    "0.31", "0.45", "0.53", "0.60",
    "0.68", "0.75", "0.94", "1.13",
    "1.30", "1.50", "1.70", "1.88"
)


def _field(value, shift, width):
    return (value >> shift) & ((1 << width) - 1)


def _decoded(name, raw, meanings):
    return "{}={} ({})".format(name, raw, meanings[raw])


def _active_flags(value, names):
    active = [name for bit, name in names if value & (1 << bit)]
    return "active: {}".format(", ".join(active)) if active else "no flags set"


def _decode_fault_status_1(value):
    return _active_flags(value, (
        (0, "VDS_LC"),
        (1, "VDS_HC"),
        (2, "VDS_LB"),
        (3, "VDS_HB"),
        (4, "VDS_LA"),
        (5, "VDS_HA"),
        (6, "OTSD"),
        (7, "UVLO"),
        (8, "GDF"),
        (9, "VDS_OCP"),
        (10, "FAULT")
    ))


def _decode_vgs_status_2(value):
    return _active_flags(value, (
        (0, "VGS_LC"),
        (1, "VGS_HC"),
        (2, "VGS_LB"),
        (3, "VGS_HB"),
        (4, "VGS_LA"),
        (5, "VGS_HA"),
        (6, "CPUV"),
        (7, "OTW"),
        (8, "SC_OC"),
        (9, "SB_OC"),
        (10, "SA_OC")
    ))


def _decode_driver_control(value):
    fields = []
    if value & (1 << 10):
        fields.append("RESERVED=1")
    fields.extend((
        _decoded("DIS_CPUV", _field(value, 9, 1), ("fault enabled", "fault disabled")),
        _decoded("DIS_GDF", _field(value, 8, 1), ("fault enabled", "fault disabled")),
        _decoded("OTW_REP", _field(value, 7, 1), ("not reported", "reported")),
        _decoded("PWM_MODE", _field(value, 5, 2), ("6x PWM", "3x PWM", "1x PWM", "independent PWM")),
        _decoded("1PWM_COM", _field(value, 4, 1), ("synchronous rectification", "asynchronous rectification")),
        "1PWM_DIR={}".format(_field(value, 3, 1)),
        _decoded("COAST", _field(value, 2, 1), ("off", "Hi-Z")),
        _decoded("BRAKE", _field(value, 1, 1), ("off", "low-side MOSFETs on")),
        _decoded("CLR_FLT", _field(value, 0, 1), ("idle", "clear faults"))
    ))
    return ", ".join(fields)


def _decode_gate_drive_hs(value):
    lock = _field(value, 8, 3)
    lock_meaning = {3: "unlock", 6: "lock"}.get(lock, "no effect")
    source = _field(value, 4, 4)
    sink = _field(value, 0, 4)
    return ", ".join((
        "LOCK={} ({})".format(lock, lock_meaning),
        "IDRIVEP_HS={} ({} mA source)".format(source, SOURCE_CURRENT_MA[source]),
        "IDRIVEN_HS={} ({} mA sink)".format(sink, SINK_CURRENT_MA[sink])
    ))


def _decode_gate_drive_ls(value):
    tdrive = _field(value, 8, 2)
    source = _field(value, 4, 4)
    sink = _field(value, 0, 4)
    return ", ".join((
        _decoded("CBC", _field(value, 10, 1), ("disabled", "enabled")),
        _decoded("TDRIVE", tdrive, ("500 ns", "1000 ns", "2000 ns", "4000 ns")),
        "IDRIVEP_LS={} ({} mA source)".format(source, SOURCE_CURRENT_MA[source]),
        "IDRIVEN_LS={} ({} mA sink)".format(sink, SINK_CURRENT_MA[sink])
    ))


def _decode_ocp_control(value):
    return ", ".join((
        _decoded("TRETRY", _field(value, 10, 1), ("4 ms", "50 us")),
        _decoded("DEAD_TIME", _field(value, 8, 2), ("50 ns", "100 ns", "200 ns", "400 ns")),
        _decoded("OCP_MODE", _field(value, 6, 2), ("latched shutdown", "automatic retry", "report only", "disabled")),
        _decoded("OCP_DEG", _field(value, 4, 2), ("2 us", "4 us", "6 us", "8 us")),
        _decoded("VDS_LVL", _field(value, 0, 4), tuple("{} V".format(level) for level in VDS_LEVEL_V))
    ))


def _decode_csa_control(value):
    return ", ".join((
        _decoded("CSA_FET", _field(value, 10, 1), ("SPx input", "SHx input")),
        _decoded("VREF_DIV", _field(value, 9, 1), ("VREF", "VREF / 2")),
        _decoded("LS_REF", _field(value, 8, 1), ("SHx-SPx", "SHx-SNx")),
        _decoded("CSA_GAIN", _field(value, 6, 2), ("5 V/V", "10 V/V", "20 V/V", "40 V/V")),
        _decoded("DIS_SEN", _field(value, 5, 1), ("sense OCP enabled", "sense OCP disabled")),
        _decoded("CSA_CAL_A", _field(value, 4, 1), ("normal", "inputs shorted")),
        _decoded("CSA_CAL_B", _field(value, 3, 1), ("normal", "inputs shorted")),
        _decoded("CSA_CAL_C", _field(value, 2, 1), ("normal", "inputs shorted")),
        _decoded("SEN_LVL", _field(value, 0, 2), ("0.25 V", "0.50 V", "0.75 V", "1.00 V"))
    ))


REGISTERS = {
    0x0: ("FAULT_STATUS_1", "R", _decode_fault_status_1),
    0x1: ("VGS_STATUS_2", "R", _decode_vgs_status_2),
    0x2: ("DRIVER_CONTROL", "RW", _decode_driver_control),
    0x3: ("GATE_DRIVE_HS", "RW", _decode_gate_drive_hs),
    0x4: ("GATE_DRIVE_LS", "RW", _decode_gate_drive_ls),
    0x5: ("OCP_CONTROL", "RW", _decode_ocp_control),
    0x6: ("CSA_CONTROL", "RW", _decode_csa_control),
    0x7: ("RESERVED", "RW", lambda value: "reserved data=0x{:03X}".format(value))
}


class Hla(HighLevelAnalyzer):
    """Decode one DRV8323S 16-clock transaction into one Saleae frame."""

    result_types = {
        "transaction": {
            "format": "{{data.summary}}",
        },
        "error": {
            "format": "DRV8323S ERROR: {{data.message}}",
        },
    }

    def __init__(self):
        self._reset()

    def _reset(self):
        self._mosi = []
        self._miso = []
        self._word_start = None

    @staticmethod
    def _as_bytes(data, key):
        value = data.get(key)
        if value is None:
            return ()
        if isinstance(value, int):
            return (value & 0xFF,)
        return tuple(value)

    @staticmethod
    def _error(start_time, end_time, message):
        return AnalyzerFrame("error", start_time, end_time, {"message": message})

    @staticmethod
    def _transaction(start_time, end_time, command, response):
        operation = "READ" if command & 0x8000 else "WRITE"
        address = (command >> 11) & 0xF
        write_data = command & 0x07FF
        response_data = None if response is None else response & 0x07FF

        register = REGISTERS.get(address)
        if register is None:
            register_name = "UNKNOWN_0x{:X}".format(address)
            access = "?"
            decoder = lambda value: "unmapped register data=0x{:03X}".format(value)
        else:
            register_name, access, decoder = register

        warnings = []
        if operation == "WRITE" and access == "R":
            warnings.append("write to read-only register")
        if address == 0x7:
            warnings.append("reserved register")
        if address > 0x7:
            warnings.append("unmapped register")

        if operation == "READ":
            value = response_data
            if value is None:
                bitfields = "SDO/MISO not captured"
                action = "=> ---"
            else:
                bitfields = decoder(value)
                action = "=> 0x{:03X}".format(value)
        else:
            value = write_data
            bitfields = decoder(value)
            action = "<= 0x{:03X}".format(value)
            if response_data is not None:
                action += " (previous 0x{:03X})".format(response_data)

        return AnalyzerFrame("transaction", start_time, end_time, {
            "operation": operation,
            "register": register_name,
            "address": "0x{:X}".format(address),
            "value": "---" if value is None else "0x{:03X}".format(value),
            "bitfields": bitfields,
            "mosi": "0x{:04X}".format(command),
            "miso": "---" if response is None else "0x{:04X}".format(response),
        })

    def decode(self, frame):
        # with nSCS configured, Saleae supplies enable/disable frames
        # reset on enable so a partial capture cannot contaminate the next transaction.
        if frame.type == "enable":
            self._reset()
            self._word_start = frame.start_time
            return None

        if frame.type == "error":
            self._reset()
            return self._error(frame.start_time, frame.end_time, "low-level SPI framing error")

        if frame.type == "disable":
            if self._mosi:
                start_time = self._word_start or frame.start_time
                bit_count = len(self._mosi) * 8
                self._reset()
                return self._error(
                    start_time,
                    frame.end_time,
                    "incomplete {}-bit word; expected 16 bits".format(bit_count),
                )
            self._reset()
            return None

        if frame.type != "result":
            return None

        data = frame.data if isinstance(frame.data, dict) else {}
        mosi = self._as_bytes(data, "mosi")
        miso = self._as_bytes(data, "miso")
        if not mosi:
            return self._error(frame.start_time, frame.end_time,
                               "MOSI/SDI is required to decode the command")

        if self._word_start is None:
            self._word_start = frame.start_time

        for index, byte in enumerate(mosi):
            self._mosi.append(byte)
            self._miso.append(miso[index] if index < len(miso) else None)

        decoded = []
        while len(self._mosi) >= 2:
            command = (self._mosi[0] << 8) | self._mosi[1]
            if self._miso[0] is None or self._miso[1] is None:
                response = None
            else:
                response = (self._miso[0] << 8) | self._miso[1]

            decoded.append(self._transaction(
                self._word_start, frame.end_time, command, response
            ))
            del self._mosi[:2]
            del self._miso[:2]
            self._word_start = frame.start_time if self._mosi else None

        if not decoded:
            return None
        return decoded[0] if len(decoded) == 1 else decoded
