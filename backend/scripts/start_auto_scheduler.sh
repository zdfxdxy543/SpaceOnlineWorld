#!/bin/bash

###############################################################################
# Auto Scheduler Runner Startup Script for Ubuntu
#
# This script starts the auto_scheduler_runner.py and keeps it running
# continuously in the background.
#
# Usage:
#   ./start_auto_scheduler.sh [OPTIONS]
#
# Options:
#   --base-url BASE_URL    Base URL of the API server (default: http://localhost:8000)
#   --actors ACTORS        Comma-separated actor ids (default: empty)
#   --cycles CYCLES        Number of dispatch cycles per run (default: 1)
#   --stop                 Stop the running scheduler
#   --status               Check if scheduler is running
#   --logs                 View the scheduler logs
#
###############################################################################

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$SCRIPT_DIR/auto_scheduler_runner.py"
PID_FILE="$SCRIPT_DIR/.auto_scheduler.pid"
LOG_FILE="$SCRIPT_DIR/.auto_scheduler.log"

# Default values
BASE_URL="http://localhost:8000"
ACTORS=""
CYCLES=1

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --base-url BASE_URL    Base URL of the API server (default: http://localhost:8000)"
    echo "  --actors ACTORS        Comma-separated actor ids (default: empty)"
    echo "  --cycles CYCLES        Number of dispatch cycles per run (default: 1)"
    echo "  --stop                 Stop the running scheduler"
    echo "  --status               Check if scheduler is running"
    echo "  --logs                 View the scheduler logs"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Start with default settings"
    echo "  $0 --actors aria,milo                 # Start with specific actors"
    echo "  $0 --cycles 3                         # Run 3 cycles per scheduler execution"
    echo "  $0 --stop                             # Stop the running scheduler"
    echo "  $0 --logs                             # View logs in real-time"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "python3 is not installed. Please install python3 first."
        exit 1
    fi
}

check_scheduler_script() {
    if [ ! -f "$PYTHON_SCRIPT" ]; then
        log_error "Scheduler script not found: $PYTHON_SCRIPT"
        exit 1
    fi
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

start_scheduler() {
    log_info "Starting Auto Scheduler Runner..."
    
    # Build command
    CMD="python3 $PYTHON_SCRIPT --base-url $BASE_URL --cycles $CYCLES"
    if [ -n "$ACTORS" ]; then
        CMD="$CMD --actors $ACTORS"
    fi
    
    # Start in background
    cd "$PROJECT_ROOT"
    nohup $CMD > "$LOG_FILE" 2>&1 &
    PID=$!
    
    # Save PID
    echo $PID > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 2
    if ps -p $PID > /dev/null 2>&1; then
        log_success "Auto Scheduler Runner started successfully (PID: $PID)"
        log_info "Logs are being written to: $LOG_FILE"
        log_info "To view logs: $0 --logs"
        log_info "To stop: $0 --stop"
    else
        log_error "Failed to start Auto Scheduler Runner. Check logs: $LOG_FILE"
        exit 1
    fi
}

stop_scheduler() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        log_info "Stopping Auto Scheduler Runner (PID: $PID)..."
        kill $PID 2>/dev/null || true
        
        # Wait for process to stop
        for i in {1..10}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            log_warning "Process did not stop gracefully, forcing..."
            kill -9 $PID 2>/dev/null || true
        fi
        
        rm -f "$PID_FILE"
        log_success "Auto Scheduler Runner stopped"
    else
        log_warning "Auto Scheduler Runner is not running"
    fi
}

show_status() {
    if is_running; then
        PID=$(cat "$PID_FILE")
        UPTIME=$(ps -p $PID -o etime= | xargs)
        log_success "Auto Scheduler Runner is running (PID: $PID, Uptime: $UPTIME)"
        
        # Show recent log entries
        if [ -f "$LOG_FILE" ]; then
            echo ""
            log_info "Recent logs:"
            tail -n 5 "$LOG_FILE" | sed 's/^/  /'
        fi
    else
        log_warning "Auto Scheduler Runner is not running"
    fi
}

view_logs() {
    if [ -f "$LOG_FILE" ]; then
        log_info "Viewing logs (Ctrl+C to exit):"
        tail -f "$LOG_FILE"
    else
        log_warning "No log file found"
    fi
}

# Parse arguments
STOP=false
STATUS=false
LOGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --actors)
            ACTORS="$2"
            shift 2
            ;;
        --cycles)
            CYCLES="$2"
            shift 2
            ;;
        --stop)
            STOP=true
            shift
            ;;
        --status)
            STATUS=true
            shift
            ;;
        --logs)
            LOGS=true
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Main logic
check_python
check_scheduler_script

if $STOP; then
    stop_scheduler
elif $STATUS; then
    show_status
elif $LOGS; then
    view_logs
elif is_running; then
    log_warning "Auto Scheduler Runner is already running"
    show_status
    exit 0
else
    start_scheduler
fi
