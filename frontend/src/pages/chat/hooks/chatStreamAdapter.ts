export type ChatRunToken = number;

export function createChatRunLifecycle() {
  let mounted = true;
  let activeRun: ChatRunToken | null = null;
  let nextRun = 0;
  return {
    mount(): void {
      mounted = true;
    },
    begin(): ChatRunToken | null {
      if (!mounted || activeRun !== null) return null;
      activeRun = ++nextRun;
      return activeRun;
    },
    isActive(run: ChatRunToken): boolean {
      return mounted && activeRun === run;
    },
    stop(run: ChatRunToken): void {
      if (activeRun === run) activeRun = null;
    },
    dispose(): void {
      mounted = false;
      activeRun = null;
    },
  };
}
