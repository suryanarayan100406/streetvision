import { useFetch } from '../hooks/useFetch';
import api from '../api';
import toast from 'react-hot-toast';
import { useState } from 'react';

export default function Settings() {
  const { data: settings, refetch } = useFetch('/admin/settings/');
  const { data: contacts } = useFetch('/admin/settings/contacts/government');
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState('');

  const startEdit = (s) => {
    setEditing(s.key);
    setEditValue(s.value || '');
  };

  const saveEdit = async (key) => {
    await api.put(`/admin/settings/${key}`, { value: editValue });
    toast.success('Setting updated');
    setEditing(null);
    refetch();
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">System Settings</h2>

      <div className="bg-white rounded-xl border overflow-hidden mb-8">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Key</th>
              <th className="text-left px-4 py-3">Category</th>
              <th className="text-left px-4 py-3">Value</th>
              <th className="text-left px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {settings?.map((s) => (
              <tr key={s.key} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{s.key}</td>
                <td className="px-4 py-3 text-gray-500">{s.category}</td>
                <td className="px-4 py-3">
                  {editing === s.key ? (
                    <input
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      className="border rounded px-2 py-1 w-full"
                      autoFocus
                    />
                  ) : (
                    <span className="truncate max-w-xs block">{s.value || '—'}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {editing === s.key ? (
                    <div className="flex gap-2">
                      <button onClick={() => saveEdit(s.key)} className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded">Save</button>
                      <button onClick={() => setEditing(null)} className="text-xs bg-gray-100 px-2 py-1 rounded">Cancel</button>
                    </div>
                  ) : (
                    <button onClick={() => startEdit(s)} className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">Edit</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Government contacts */}
      <h3 className="text-lg font-semibold mb-3">Government Contacts</h3>
      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Level</th>
              <th className="text-left px-4 py-3">Department</th>
              <th className="text-left px-4 py-3">Name</th>
              <th className="text-left px-4 py-3">Designation</th>
              <th className="text-left px-4 py-3">Email</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {contacts?.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{c.authority_level}</td>
                <td className="px-4 py-3">{c.department}</td>
                <td className="px-4 py-3">{c.name}</td>
                <td className="px-4 py-3">{c.designation}</td>
                <td className="px-4 py-3 text-gray-500">{c.email}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
