export async function api<T = any>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.message || value.error || 'Request failed');
  return value;
}
export interface Document { id: string; revision: number; title: string; characters: number; text?: string }
export interface Node { id: string; label: string }
export interface Edge { source: string; target: string; relation: string; claim_id: string; chunk_id: string; support: string }
export interface Community { id: string; nodes: string[]; claim_ids: string[] }
export interface Graph { generation: number; nodes: Node[]; edges: Edge[]; communities: Community[] }
export interface Passage { chunk_id: string; document_id: string; revision: number; text: string; title: string; citation?: string }
export interface Run { id: string; mode: string; status: string; error?: string; calls: any[]; result: any; generation: number }
