import os
import sys
import time
import ctypes
from ctypes import wintypes
import requests

WEBHOOK_URL = "https://hollowdrive-reporter.samucalata.workers.dev"

def monitor_process(pid, log_path):
    if os.name != 'nt':
        return

    SYNCHRONIZE = 0x00100000
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32

    handle = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return

    INFINITE = 0xFFFFFFFF
    kernel32.WaitForSingleObject(handle, INFINITE)

    exit_code = wintypes.DWORD()
    kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)

    code_val = exit_code.value
    time.sleep(0.5)

    log_content = ""
    crash_detected = False
    crash_reason = ""

    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                log_content = "".join(lines)
                tail_lines = lines[-50:] if len(lines) > 50 else lines
                tail_text = "".join(tail_lines)

                crash_keywords = [
                    "Fatal Python error",
                    "PyEval_RestoreThread",
                    "Traceback (most recent call last)",
                    "CRASH NO CONTROLADO",
                    "CRASH FATAL",
                    "Segmentation fault",
                    "Access violation"
                ]
                for kw in crash_keywords:
                    if kw in tail_text:
                        crash_detected = True
                        crash_reason = kw
                        break
        except Exception:
            pass

    if code_val != 0 or crash_detected:
        try:
            hex_code = f"0x{code_val:08X}" if code_val > 255 or code_val < 0 else str(code_val)
            motivo = crash_reason if crash_reason else f"Código de salida anormal ({hex_code})"

            extracto = "\n".join(log_content.strip().splitlines()[-12:]) if log_content else "No hay contenido de log disponible."
            if len(extracto) > 1000:
                extracto = extracto[-1000:]

            payload = {
                "content": (
                    f"🚨 **¡CRASH / TERMINACIÓN ANORMAL DETECTADA POR EL WATCHDOG!**\n"
                    f"🖥️ **PID Monitoreado:** `{pid}` | **Código:** `{hex_code}`\n"
                    f"⚠️ **Motivo Detectado:** `{motivo}`\n"
                    f"```text\n{extracto}\n```"
                )
            }

            if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                with open(log_path, "rb") as f:
                    files = {"file": (os.path.basename(log_path), f, "text/plain")}
                    requests.post(WEBHOOK_URL, data=payload, files=files, timeout=20)
            else:
                requests.post(WEBHOOK_URL, json=payload, timeout=20)
        except Exception:
            pass

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        target_pid = sys.argv[1]
        target_log = sys.argv[2]
        monitor_process(target_pid, target_log)
