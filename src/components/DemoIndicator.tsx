import { useState, useEffect } from 'react';
import { WifiOff } from 'lucide-react';
import { isMockMode } from '../services/api';

export default function DemoIndicator() {
  const [mock, setMock] = useState(false);

  useEffect(() => {
    // Check after a short delay to let API calls determine mode
    const timer = setTimeout(() => {
      setMock(isMockMode());
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  if (!mock) return null;

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
      <WifiOff className="w-3 h-3" />
      <span>Demo</span>
    </div>
  );
}
