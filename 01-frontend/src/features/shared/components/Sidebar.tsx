import { useEffect, useState } from 'react';
import { NavLink } from 'react-router';
import {
  History,
  LayoutDashboard,
  MessagesSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Users,
} from 'lucide-react';

import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { ICON } from '../icons';

const NAV = [
  { to: '/dashboard', label: 'Dashboard', Icon: LayoutDashboard },
  { to: '/chat', label: 'Chat', Icon: MessagesSquare },
  { to: '/teams', label: 'Teams', Icon: Users },
  { to: '/history', label: 'History', Icon: History },
];

/** Remembered across reloads: a collapsed rail is a working preference, and
 * having to fold it again on every refresh is what makes people stop using it. */
const STORAGE_KEY = 'hivemind.sidebar.collapsed';

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(STORAGE_KEY) === '1',
  );
  const { data: health } = useAsync(() => api.health(), []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  return (
    <nav
      className={`flex shrink-0 flex-col border-r border-line bg-surface transition-[width] duration-200 ${
        collapsed ? 'w-14' : 'w-56'
      }`}
    >
      <div
        className={`flex items-center gap-2 border-b border-line py-6 ${
          collapsed ? 'justify-center px-0' : 'px-5'
        }`}
      >
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-lg font-medium tracking-tight text-paper">
              Hive Mind
            </p>
            <p className="edge-mark mt-1 text-faint">Local arena</p>
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
          className="cursor-pointer rounded-sm p-1.5 text-faint transition-colors hover:text-paper"
        >
          {collapsed ? <PanelLeftOpen {...ICON} /> : <PanelLeftClose {...ICON} />}
        </button>
      </div>

      <ul className="flex-1 py-3">
        {NAV.map(({ to, label, Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              // The label is the tooltip only while collapsed: doubling it as a
              // hover hint next to visible text is noise.
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `relative flex items-center gap-3 py-2.5 text-sm transition-colors ${
                  collapsed ? 'justify-center px-0' : 'px-5'
                } ${
                  isActive
                    ? 'text-paper before:absolute before:top-2 before:bottom-2 before:left-0 before:w-0.5 before:bg-signal'
                    : 'text-muted hover:text-paper'
                }`
              }
            >
              <Icon {...ICON} className="shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className={`border-t border-line py-4 ${collapsed ? 'px-0' : 'px-5'}`}>
        {!collapsed && <p className="edge-mark mb-2 text-faint">Local engines</p>}
        {health ? (
          <ul className={`space-y-1.5 ${collapsed ? 'flex flex-col items-center' : ''}`}>
            {health.engines.map((engine) => (
              <li
                key={engine.provider}
                // Collapsed, the dot is all that is left, so it has to carry the
                // name and the state on its own.
                title={collapsed ? `${engine.label}: ${engine.available ? 'up' : 'down'}` : undefined}
                className="flex items-center gap-2 text-xs text-muted"
              >
                <span
                  aria-hidden
                  className={`size-1.5 shrink-0 rounded-full ${
                    engine.available ? 'bg-sky' : 'bg-faint'
                  }`}
                />
                {!collapsed && <span className="truncate">{engine.label}</span>}
                {collapsed && <span className="sr-only">{engine.label}</span>}
              </li>
            ))}
          </ul>
        ) : (
          !collapsed && <p className="text-xs text-faint">Checking...</p>
        )}
      </div>
    </nav>
  );
}
