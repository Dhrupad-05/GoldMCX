export function DataState({
  loading,
  error,
  empty,
  skeleton,
  retry,
}: {
  loading: boolean
  error: string | null
  empty?: string
  skeleton?: React.ReactNode
  retry?: () => void
}) {
  if (loading) {
    return (
      <>
        {skeleton ?? (
          <div className="rounded-lg bg-appBg border border-border animate-pulse h-32" />
        )}
      </>
    )
  }
  if (error) {
    return (
      <div className="rounded-lg bg-[#B33838]/10 border border-[#B33838]/25 p-4 text-center">
        <p className="text-[12.5px] font-semibold text-[#8C2B2B]">Could not load data</p>
        <p className="text-[11.5px] text-[#8C2B2B]/80 mt-1 leading-relaxed">{error}</p>
        {retry && (
          <button
            onClick={retry}
            className="mt-3 text-[12px] font-semibold text-maroon hover:underline"
          >
            Retry
          </button>
        )}
      </div>
    )
  }
  if (empty) {
    return (
      <div className="rounded-lg bg-appBg border border-border p-4 text-center">
        <p className="text-[12px] text-muted leading-relaxed">{empty}</p>
      </div>
    )
  }
  return null
}
