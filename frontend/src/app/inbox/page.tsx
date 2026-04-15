"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Email {
  id: number;
  job_id: number | null;
  from_address: string;
  to_address: string;
  subject: string;
  body_preview: string;
  email_type: string;
  received_date: string;
  action_needed: string | null;
}

interface Assessment {
  id: number;
  job_id: number | null;
  platform: string;
  oa_link: string;
  deadline: string | null;
  status: string;
  company: string | null;
  title: string | null;
}

const TYPE_COLORS: Record<string, string> = {
  assessment: "bg-yellow-100 text-yellow-800",
  verification: "bg-blue-100 text-blue-800",
  rejection: "bg-red-100 text-red-800",
  general: "bg-gray-100 text-gray-800",
};

export default function InboxPage() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [tab, setTab] = useState<"emails" | "assessments">("emails");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    loadEmails();
    loadAssessments();
  }, [typeFilter]);

  async function loadEmails() {
    const params = typeFilter ? `?email_type=${typeFilter}` : "";
    const data = await api<Email[]>(`/api/emails${params}`);
    setEmails(data);
  }

  async function loadAssessments() {
    const data = await api<Assessment[]>("/api/emails/assessments");
    setAssessments(data);
  }

  async function fetchNow() {
    setFetching(true);
    try {
      await api("/api/emails/fetch", { method: "POST" });
      await loadEmails();
      await loadAssessments();
    } finally {
      setFetching(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Inbox</h1>
        <button
          onClick={fetchNow}
          disabled={fetching}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {fetching ? "Fetching..." : "Fetch Emails"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 mb-4 border-b">
        <button
          onClick={() => setTab("emails")}
          className={`px-4 py-2 text-sm font-medium ${
            tab === "emails"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Emails ({emails.length})
        </button>
        <button
          onClick={() => setTab("assessments")}
          className={`px-4 py-2 text-sm font-medium ${
            tab === "assessments"
              ? "border-b-2 border-blue-600 text-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Assessments ({assessments.length})
        </button>
      </div>

      {tab === "emails" && (
        <>
          {/* Type filter */}
          <div className="flex space-x-2 mb-4">
            {["", "assessment", "verification", "rejection", "general"].map(
              (t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`px-3 py-1 rounded text-xs font-medium ${
                    typeFilter === t
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  {t || "All"}
                </button>
              )
            )}
          </div>

          {emails.length === 0 ? (
            <p className="text-gray-500">
              No emails yet. Configure GMAIL_ADDRESS and GMAIL_APP_PASSWORD in
              .env, then click Fetch Emails.
            </p>
          ) : (
            <div className="space-y-2">
              {emails.map((em) => (
                <div
                  key={em.id}
                  className="border rounded p-4 hover:bg-gray-50"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${
                            TYPE_COLORS[em.email_type] || TYPE_COLORS.general
                          }`}
                        >
                          {em.email_type}
                        </span>
                        {em.job_id && (
                          <a
                            href={`/jobs/${em.job_id}`}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            Job #{em.job_id}
                          </a>
                        )}
                      </div>
                      <p className="font-medium text-sm truncate">
                        {em.subject}
                      </p>
                      <p className="text-xs text-gray-500 truncate">
                        From: {em.from_address}
                      </p>
                      {em.action_needed && (
                        <p className="text-xs text-orange-600 mt-1 font-medium">
                          Action: {em.action_needed}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-gray-400 whitespace-nowrap ml-4">
                      {em.received_date}
                    </span>
                  </div>
                  {em.body_preview && (
                    <p className="mt-2 text-xs text-gray-600 line-clamp-2">
                      {em.body_preview.slice(0, 200)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "assessments" && (
        <>
          {assessments.length === 0 ? (
            <p className="text-gray-500">No assessments detected yet.</p>
          ) : (
            <div className="space-y-2">
              {assessments.map((a) => (
                <div key={a.id} className="border rounded p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                        {a.platform}
                      </span>
                      <span
                        className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${
                          a.status === "PENDING"
                            ? "bg-orange-100 text-orange-800"
                            : a.status === "COMPLETED"
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {a.status}
                      </span>
                      <p className="font-medium text-sm mt-1">
                        {a.company} — {a.title}
                      </p>
                      <a
                        href={a.oa_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline break-all"
                      >
                        {a.oa_link}
                      </a>
                    </div>
                    {a.deadline && (
                      <span className="text-xs text-red-600 font-medium whitespace-nowrap ml-4">
                        Due: {a.deadline}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
