"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../../lib/api";

interface Job {
  id: number;
  company: string;
  title: string;
  location: string | null;
  score: number;
  status: string;
  date_found: string | null;
  description: string | null;
}

export default function ReviewPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api<Job[]>("/api/jobs?status=REVIEW_NEEDED")
      .then(setJobs)
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const updateStatus = async (id: number, status: string) => {
    await api(`/api/jobs/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    load();
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Review Queue</h1>
      <p className="text-sm text-gray-500 mb-6">
        Jobs that need your manual decision — approve or skip.
      </p>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : jobs.length === 0 ? (
        <p className="text-gray-500">No jobs to review. All clear!</p>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <div key={job.id} className="bg-white shadow rounded-lg p-4">
              <div className="flex justify-between items-start">
                <div>
                  <Link
                    href={`/jobs/${job.id}`}
                    className="text-lg font-semibold text-blue-600 hover:underline"
                  >
                    {job.title}
                  </Link>
                  <p className="text-sm text-gray-600">{job.company}</p>
                  {job.location && (
                    <p className="text-xs text-gray-500">{job.location}</p>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-xl font-bold">{job.score}</div>
                  <div className="text-xs text-gray-500">Score</div>
                </div>
              </div>
              {job.description && (
                <p className="text-sm text-gray-600 mt-2 line-clamp-3">
                  {job.description}
                </p>
              )}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => updateStatus(job.id, "MATCHED")}
                  className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                >
                  Approve
                </button>
                <button
                  onClick={() => updateStatus(job.id, "SKIPPED")}
                  className="px-4 py-1.5 bg-gray-300 rounded text-sm hover:bg-gray-400"
                >
                  Skip
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
