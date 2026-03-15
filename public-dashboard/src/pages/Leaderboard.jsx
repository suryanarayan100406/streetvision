import useFetch from '../hooks/useFetch';

export default function Leaderboard() {
  const { data: leaderboard, loading, error } = useFetch('/api/dashboard/leaderboard');

  if (loading) return <div className="text-center py-8">Loading...</div>;
  if (error) {
    return (
      <div className="text-center py-8 text-red-600">
        Leaderboard could not be loaded. Check API host/network and try again.
      </div>
    );
  }

  if (!Array.isArray(leaderboard) || leaderboard.length === 0) {
    return (
      <div className="text-center py-8 text-gray-600">
        No leaderboard data yet. Submit reports to generate rankings.
      </div>
    );
  }

  const medals = ['🥇', '🥈', '🥉'];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Gamification Leaderboard</h2>

      <div className="grid lg:grid-cols-3 gap-4">
        {leaderboard.slice(0, 3).map((user, idx) => (
          <div
            key={user.user_id || idx}
            className={`p-6 rounded-xl text-white text-center ${
              idx === 0 ? 'bg-gradient-to-br from-yellow-400 to-yellow-500' :
              idx === 1 ? 'bg-gradient-to-br from-gray-400 to-gray-500' :
              'bg-gradient-to-br from-orange-400 to-orange-500'
            }`}
          >
            <p className="text-4xl mb-2">{medals[idx] || `#${idx + 1}`}</p>
            <p className="font-bold text-lg">{user.display_name || user.user_id}</p>
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
            {leaderboard.map((user, index) => (
              <tr key={user.user_id || `${user.rank || index}`} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-bold">{user.rank}</td>
                <td className="px-4 py-3">{user.display_name || user.user_id}</td>
                <td className="px-4 py-3">{user.reports_count}</td>
                <td className="px-4 py-3 font-semibold">{user.total_points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
