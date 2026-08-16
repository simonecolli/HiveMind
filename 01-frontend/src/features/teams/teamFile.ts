import type { TeamExport } from '../shared/api/types';

/** `Board of Directors` -> `board-of-directors.hivemind.json` */
export function fileNameFor(team: TeamExport): string {
  const slug =
    team.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '') || 'team';
  return `${slug}.hivemind.json`;
}

export function downloadTeam(team: TeamExport): void {
  const blob = new Blob([JSON.stringify(team, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileNameFor(team);
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function readTeamFile(file: File): Promise<unknown> {
  const text = await file.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${file.name} is not valid JSON.`);
  }
}
