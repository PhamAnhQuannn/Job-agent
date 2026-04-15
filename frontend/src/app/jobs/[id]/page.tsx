"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../lib/api";

interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  description: string | null;
  source: string | null;
  source_url: string | null;
  score: number;
  status: string;
  date_found: string | null;
  date_applied: string | null;
  email_used: string | null;
  cover_letter_path: string | null;
  screenshot_path: string | null;
  failure_step: string | null;
  notes: string | null;
}

const ALL_STATUSES = [
  "FOUND", "MATCHED", "REVIEW_NEEDED", "DRAFTED", "APPLYING",
  "SUBMITTED", "FAILED", "SKIPPED", "DUPLICATE", "REJECTED",
  "INTERVIEW", "OFFER", "WITHDRAWN",
];

export default function JobDetailPage() {
  const params = useParams();
  const jobId = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [updating, setUpdating] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api<Job>(`/api/jobs/${jobId}`).then(setJob);
  }, [jobId]);

  const updateStatus = async (status: string) => {
    setUpdating(true);
    setMsg("");
    try {
      const updated = await api<Job>(`/api/jobs/${jobId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setJob(updated);
      setMsg(`Status updated to ${status}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Update failed");
    } finally {
      setUpdating(false);
    }
  };

  if (!job) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="mb-4">
        <a href="/jobs" className="text-sm text-blue-600 hover:underline">
          ← Back to Jobs
        </a>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-2xl font-bold">{job.title}</h1>
            <p className="text-gray-600">{job.company}</p>
            {job.location && (
              <p className="text-sm text-gray-500">{job.location}</p>
            )}
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold">{job.score}</div>
            <div className="text-xs text-gray-500">Score</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm mb-6">
          <div>
            <span className="font-medium text-gray-600">Status: </span>
            <span className="font-semibold">{job.status}</span>
          </div>
          <div>
            <span className="font-medium text-gray-600">Source: </span>
            {job.source_url ? (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                {job.source || "Link"}
              </a>
            ) : (
              <span>{job.source || "—"}</span>
            )}
          </div>
          <div>
            <span className="font-medium text-gray-600">Found: </span>
            <span>
              {job.date_found
                ? new Date(job.date_found).toLocaleString()
                : "—"}
            </span>
          </div>
          <div>
            <span className="font-medium text-gray-600">Applied: </span>
            <span>
              {job.date_applied
                ? new Date(job.date_applied).toLocaleString()
                : "—"}
            </span>
          </div>
          {job.email_used && (
            <div>
              <span className="font-medium text-gray-600">Email: </span>
              <span>{job.email_used}</span>
            </div>
          )}
          {job.failure_step && (
            <div>
              <span className="font-medium text-gray-600">Failed at: </span>
              <span className="text-red-600">{job.failure_step}</span>
            </div>
          )}
        </div>

        {job.notes && (
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-1">Notes</h3>
            <p className="text-sm bg-gray-50 p-3 rounded">{job.notes}</p>
          </div>
        )}

        {job.description && (
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-600 mb-1">
              Description
            </h3>
            <div className="text-sm bg-gray-50 p-4 rounded whitespace-pre-wrap max-h-96 overflow-auto">
              {job.description}
            </div>
          </div>
        )}

        <div className="border-t pt-4">
          <h3 className="text-sm font-medium text-gray-600 mb-2">
            Update Status
          </h3>
          {msg && <p className="text-sm text-green-600 mb-2">{msg}</p>}
          <div className="flex flex-wrap gap-2">
            {ALL_STATUSES.filter((s) => s !== job.status).map((s) => (
              <button
                key={s}
                onClick={() => updateStatus(s)}
                disabled={updating}
                className="px-3 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
