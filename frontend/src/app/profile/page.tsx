"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";

interface Profile {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  school: string | null;
  degree: string | null;
  graduation_date: string | null;
  linkedin: string | null;
  github: string | null;
  portfolio: string | null;
  location: string | null;
  work_authorization: string | null;
  needs_sponsorship: boolean;
  willing_to_relocate: boolean;
  target_roles: string | null;
  preferred_locations: string | null;
}

const FIELDS: { key: keyof Profile; label: string; type?: string }[] = [
  { key: "full_name", label: "Full Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "school", label: "School" },
  { key: "degree", label: "Degree" },
  { key: "graduation_date", label: "Graduation Date" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "github", label: "GitHub" },
  { key: "portfolio", label: "Portfolio" },
  { key: "location", label: "Location" },
  { key: "work_authorization", label: "Work Authorization" },
  { key: "target_roles", label: "Target Roles" },
  { key: "preferred_locations", label: "Preferred Locations" },
];

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Profile>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api<Profile>("/api/profile").then((p) => {
      setProfile(p);
      setForm(p);
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      const updated = await api<Profile>("/api/profile", {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setProfile(updated);
      setEditing(false);
      setMsg("Saved!");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!profile) return <p className="text-gray-500">Loading...</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Profile</h1>
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
          >
            Edit
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setForm(profile);
              }}
              className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400 text-sm"
            >
              Cancel
            </button>
          </div>
        )}
      </div>
      {msg && <p className="mb-4 text-sm text-green-600">{msg}</p>}
      <div className="bg-white shadow rounded-lg p-6 space-y-4">
        {FIELDS.map(({ key, label }) => (
          <div key={key} className="flex flex-col sm:flex-row sm:items-center gap-1">
            <label className="w-48 text-sm font-medium text-gray-600">
              {label}
            </label>
            {editing ? (
              <input
                className="flex-1 border rounded px-3 py-1.5 text-sm"
                value={(form[key] as string) || ""}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              />
            ) : (
              <span className="text-sm">
                {(profile[key] as string) || "—"}
              </span>
            )}
          </div>
        ))}
        <div className="flex flex-col sm:flex-row sm:items-center gap-1">
          <label className="w-48 text-sm font-medium text-gray-600">
            Needs Sponsorship
          </label>
          {editing ? (
            <input
              type="checkbox"
              checked={!!form.needs_sponsorship}
              onChange={(e) =>
                setForm({ ...form, needs_sponsorship: e.target.checked })
              }
            />
          ) : (
            <span className="text-sm">
              {profile.needs_sponsorship ? "Yes" : "No"}
            </span>
          )}
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-1">
          <label className="w-48 text-sm font-medium text-gray-600">
            Willing to Relocate
          </label>
          {editing ? (
            <input
              type="checkbox"
              checked={!!form.willing_to_relocate}
              onChange={(e) =>
                setForm({ ...form, willing_to_relocate: e.target.checked })
              }
            />
          ) : (
            <span className="text-sm">
              {profile.willing_to_relocate ? "Yes" : "No"}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
