import type { ChildProcess } from 'node:child_process'

interface TrackedProcess {
  process: ChildProcess
  abortController: AbortController
}

const activeProcesses = new Map<string, TrackedProcess>()

export function trackProcess(jobId: string, process: ChildProcess, abortController: AbortController): void {
  activeProcesses.set(jobId, { process, abortController })
}

export function cancelProcess(jobId: string): boolean {
  const tracked = activeProcesses.get(jobId)
  if (!tracked) {
    return false
  }

  // Signal abort to any waiting promises
  tracked.abortController.abort()

  // Kill the child process if it's still running
  if (tracked.process && !tracked.process.killed) {
    tracked.process.kill('SIGTERM')
  }

  activeProcesses.delete(jobId)
  return true
}

export function untrackProcess(jobId: string): void {
  activeProcesses.delete(jobId)
}

export function isProcessTracked(jobId: string): boolean {
  return activeProcesses.has(jobId)
}
