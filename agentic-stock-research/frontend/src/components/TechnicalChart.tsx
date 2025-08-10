import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend)

export function TechnicalChart({ labels, closes }: { labels: string[]; closes: number[] }) {
  const data = {
    labels,
    datasets: [
      {
        label: 'Close',
        data: closes,
        borderColor: 'rgb(37, 99, 235)',
        backgroundColor: 'rgba(37, 99, 235, 0.2)',
        pointRadius: 0,
        tension: 0.35,
      },
    ],
  }
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { intersect: false, mode: 'index' as const } },
    scales: { x: { display: false }, y: { display: false } },
  }
  return (
    <div className="h-28">
      <Line data={data} options={options} />
    </div>
  )
}
