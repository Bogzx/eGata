import Link from "next/link";

export default function Page() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <div className="max-w-2xl text-center">
        <h1 className="text-5xl font-bold tracking-tight">CivicAI</h1>
        <p className="mt-4 text-xl text-muted-foreground">
          Asistentul tău pentru primărie. Spune-i ce ai nevoie, îți spune ce acte îți
          trebuie.
        </p>
      </div>
      <div className="flex gap-4">
        <Link
          href="/login"
          className="rounded-md bg-primary px-6 py-3 text-lg font-medium text-primary-foreground hover:opacity-90"
        >
          Intră în cont
        </Link>
      </div>
    </main>
  );
}
