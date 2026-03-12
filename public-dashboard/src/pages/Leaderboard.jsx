import useFetch from '../hooks/useFetch';

export default function Leaderboard() {
  const { data: leaderboard } = useFetch('/api/public/leaderboard');

  if (!leaderboard) return <div className="text-center py-8">Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Gamification Leaderboard</h2>

      <div className="grid lg:grid-cols-3 gap-4">
        {leaderboard.slice(0, 3).map((user, idx) => (
          <div
            key={user.id}
            className={`p-6 rounded-xl text-white text-center ${
              idx === 0 ? 'bg-gradient-to-br from-yellow-400 to-yellow-500' :
              idx === 1 ? 'bg-gradient-to-br from-gray-400 to-gray-500' :
              'bg-gradient-to-br from-orange-400 to-orange-500'
            }`}
          >
            <p className="text-4xl mb-2">{'🥇🥈🥉'[idx]}</p>
            <p className="font-bold text-lg">{user.username}</p>
            <p className="text-2xl font-bold mt-2">{user.total_points} pts</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-4 py-3">Rank</th>
              <th className="text-left px-4 py-3">User</th>
              <th className="text-left px-4 py-3">Reports</th>
              <th className="text-left px-4 py-3">Points</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {leaderboard.map((user, idx) => (
              <tr key={user.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-bold">{idx + 1}</td>
                <td className="px-4 py-3">{user.username}</td>
                <td className="px-4 py-3">{user.report_count}</td>
                <td className="px-4 py-3 font-semibold">{user.total_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
