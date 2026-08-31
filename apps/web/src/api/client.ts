import axios from "axios";
import type {
  Job,
  JobEvent,
  QualityReport,
  RenderManifest,
  User,
} from "../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_STORAGE_KEY = "vizr_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function wsUrl(path: string): string {
  const base = API_BASE_URL.replace(/^http/, "ws");
  const token = getToken();
  return `${base}${path}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}

const client = axios.create({ baseURL: API_BASE_URL });

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

client.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err.response?.status ?? 0;
    const detail = err.response?.data?.detail ?? err.message ?? "Unknown error";
    if (status === 401) {
      clearToken();
    }
    return Promise.reject(new ApiError(status, detail));
  }
);

// -- Auth ---------------------------------------------------------------

export async function signup(email: string, password: string): Promise<User> {
  const res = await client.post<User>("/auth/signup", { email, password });
  return res.data;
}

export async function login(email: string, password: string): Promise<string> {
  const res = await client.post<{ access_token: string }>("/auth/login/json", {
    email,
    password,
  });
  return res.data.access_token;
}

export async function getCurrentUser(): Promise<User> {
  const res = await client.get<User>("/auth/me");
  return res.data;
}

// -- Jobs -----------------------------------------------------------------

export async function createJobFromPrompt(
  prompt: string,
  provider?: string,
  apiKey?: string
): Promise<Job> {
  const res = await client.post<Job>("/jobs", {
    prompt,
    provider: provider || undefined,
    api_key: apiKey || undefined,
  });
  return res.data;
}

export async function createJobFromManual(
  visualizationType: string,
  input: Record<string, unknown>,
  title: string,
  provider?: string,
  apiKey?: string
): Promise<Job> {
  const res = await client.post<Job>("/jobs/manual", {
    visualization_type: visualizationType,
    input,
    title,
    provider: provider || undefined,
    api_key: apiKey || undefined,
  });
  return res.data;
}

export async function listJobs(): Promise<Job[]> {
  const res = await client.get<Job[]>("/jobs");
  return res.data;
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await client.get<Job>(`/jobs/${jobId}`);
  return res.data;
}

export async function getJobEvents(jobId: string): Promise<JobEvent[]> {
  const res = await client.get<JobEvent[]>(`/jobs/${jobId}/events`);
  return res.data;
}

export async function getJobManifest(jobId: string): Promise<RenderManifest> {
  const res = await client.get<RenderManifest>(`/jobs/${jobId}/manifest`);
  return res.data;
}

export async function submitManualScene(
  jobId: string,
  steps: Record<string, unknown>[],
  narration: string[]
): Promise<Job> {
  const res = await client.post<Job>(`/jobs/${jobId}/manual-scene`, { steps, narration });
  return res.data;
}

export async function refreshVideoUrl(jobId: string): Promise<Job> {
  const res = await client.post<Job>(`/jobs/${jobId}/refresh-url`);
  return res.data;
}

// -- Debug ------------------------------------------------------------------

export async function getQualityReport(jobId: string): Promise<QualityReport> {
  const res = await client.get<QualityReport>(`/debug/jobs/${jobId}/quality-report`);
  return res.data;
}

export async function getJobStages(jobId: string): Promise<Record<string, string[]>> {
  const res = await client.get<Record<string, string[]>>(`/debug/jobs/${jobId}/stages`);
  return res.data;
}

export async function getStageFile(
  jobId: string,
  stageName: string,
  fileName: string
): Promise<unknown> {
  const res = await client.get(`/debug/jobs/${jobId}/stages/${stageName}/${fileName}`);
  return res.data;
}

export default client;
