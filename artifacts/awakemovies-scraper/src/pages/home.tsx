import { Film } from "lucide-react";
import { ScraperForm } from "@/components/scraper-form";

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border bg-card/60 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 border border-primary/20">
            <Film className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight">AwakeMovies Scraper</h1>
            <p className="text-xs text-muted-foreground">
              9jarocks · NaijaPrey · Nkiri · Dramakey
            </p>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-4 py-10">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold mb-2">Paste a movie or series URL</h2>
          <p className="text-muted-foreground text-sm">
            Supports 9jarocks.com, naijaprey.tv, nkiri.com and dramakey.com
          </p>
        </div>
        <ScraperForm />
      </main>
    </div>
  );
}
