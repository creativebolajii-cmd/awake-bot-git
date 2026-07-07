import { Link } from "wouter";
import { Film } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background text-foreground gap-6">
      <Film className="w-16 h-16 text-muted-foreground opacity-40" />
      <div className="text-center space-y-2">
        <h1 className="text-5xl font-bold text-primary">404</h1>
        <p className="text-muted-foreground text-lg">Page not found</p>
      </div>
      <Link href="/">
        <Button variant="outline">Back to Scraper</Button>
      </Link>
    </div>
  );
}
