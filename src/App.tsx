import { Toaster } from "@/components/ui/toaster"
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClientInstance } from '@/lib/query-client'
import { BrowserRouter as Router, Link, Route, Routes } from 'react-router-dom';

import Dashboard from './pages/Dashboard';
import BucketDetail from './pages/BucketDetail';
import BucketPolicies from './components/policy/bucket_policies';
import GlobalUploadDropzone from './components/GlobalUploadDropzone';

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/buckets/:id" element={<BucketDetail />} />
      <Route path="/policies/bucket" element={<BucketPolicies />} />
      <Route
        path="*"
        element={
          <main className="min-h-screen bg-background flex items-center justify-center px-6">
            <div className="text-center">
              <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
              <p className="mt-2 text-sm text-muted-foreground">The page you opened does not exist.</p>
              <Link to="/" className="mt-4 inline-flex text-sm font-medium text-primary hover:underline">
                Back to dashboard
              </Link>
            </div>
          </main>
        }
      />
    </Routes>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClientInstance}>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AppRoutes />
        <GlobalUploadDropzone />
      </Router>
      <Toaster />
    </QueryClientProvider>
  )
}

export default App
