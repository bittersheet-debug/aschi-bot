"""
ASCHI BOT — SUPERVISOR & KEEP-ALIVE WATCHDOG
ASCHEN EVENT ORGANIZER
Automatically restarts ASCHI BOT if it crashes or terminates.
Ensures 24/7 continuous uptime.
"""

import sys
import time
import subprocess
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("aschi_uptime.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("watchdog")

PYTHON_EXEC = sys.executable

def run_supervisor():
    logger.info("=" * 60)
    logger.info("STARTING ASCHI BOT 24/7 KEEP-ALIVE SUPERVISOR")
    logger.info("=" * 60)
    
    restart_count = 0
    
    while True:
        start_time = time.time()
        logger.info(f"Launching ASCHI BOT instance (Restart #{restart_count})...")
        
        try:
            process = subprocess.Popen(
                [PYTHON_EXEC, "bot.py"],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            exit_code = process.wait()
            run_duration = time.time() - start_time
            
            logger.warning(
                f"ASCHI BOT exited with code {exit_code} after {run_duration:.1f}s."
            )
            
            # If terminated cleanly by user (Ctrl+C), stop
            if exit_code in (0, 130, -2):
                logger.info("Bot exited intentionally. Stopping supervisor.")
                break
                
        except KeyboardInterrupt:
            logger.info("Supervisor received KeyboardInterrupt. Stopping...")
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                pass
            break
        except Exception as e:
            logger.error(f"Supervisor error: {e}", exc_info=True)
            
        restart_count += 1
        cooldown = 3
        logger.info(f"Auto-restarting ASCHI BOT in {cooldown} seconds...")
        time.sleep(cooldown)

if __name__ == "__main__":
    run_supervisor()
