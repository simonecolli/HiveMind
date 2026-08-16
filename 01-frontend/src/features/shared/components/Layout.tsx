import type { ReactNode } from 'react';
import { Outlet } from 'react-router';

import { Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="flex h-full bg-ink">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

/** Wrapper for scrolling pages; chat uses the full height instead.
 *
 * No max width: the pages that use this are lists, grids and forms, and capping
 * them at a reading measure left most of a wide screen empty while the content
 * that needed room was the first to be truncated.
 */
export function Page({ children }: { children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="px-10 py-10">{children}</div>
    </div>
  );
}
