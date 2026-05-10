/**
 * components/SkeletonLoader.jsx
 * Reusable skeleton loading placeholders.
 */

export function CardSkeleton() {
  return (
    <div className="glass overflow-hidden animate-pulse">
      <div className="skeleton h-40 rounded-none" />
      <div className="p-4 space-y-3">
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-3 w-1/2" />
        <div className="flex gap-2">
          <div className="skeleton h-5 w-16 rounded-full" />
          <div className="skeleton h-5 w-20 rounded-full" />
        </div>
        <div className="skeleton h-1.5 rounded-full" />
        <div className="flex justify-between items-center pt-2">
          <div className="skeleton h-6 w-24" />
          <div className="skeleton h-7 w-16 rounded-lg" />
        </div>
      </div>
    </div>
  );
}

export function ResultSkeleton() {
  return (
    <div className="glass p-6 space-y-5 animate-pulse">
      <div className="text-center space-y-2">
        <div className="skeleton h-3 w-32 mx-auto" />
        <div className="skeleton h-12 w-48 mx-auto" />
        <div className="skeleton h-3 w-40 mx-auto" />
      </div>
      <div className="skeleton h-3 rounded-full" />
      <div className="skeleton h-10 w-full rounded-xl" />
    </div>
  );
}
