import { Link, useParams } from "react-router";
import { BookOpen, PenLine, BarChart3, ArrowLeft } from "lucide-react";
import { getMathTopic } from "../../features/math/data/topics";
import { Card } from "../../app/components/ui/card";
import { Button } from "../../app/components/ui/button";
import { Badge } from "../../app/components/ui/badge";

export function MathTopicPage() {
  const { topicId = "" } = useParams();
  const topic = getMathTopic(topicId);

  if (!topic) {
    return (
      <div className="p-6">
        <p className="text-destructive">Unknown topic.</p>
        <Link to="/math-tutor" className="text-sm text-primary hover:underline">
          ← Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto space-y-6 pb-8">
      <Link to="/math-tutor" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
        <ArrowLeft className="w-4 h-4" /> Math dashboard
      </Link>

      <div className="gloss-panel rounded-2xl p-6 max-w-3xl">
        <Badge className="mb-2">{topic.backendTopic}</Badge>
        <h1 className="text-2xl font-semibold mb-2">{topic.label}</h1>
        <p className="text-sm text-muted-foreground">{topic.description}</p>
      </div>

      <Card className="gloss-panel p-6 max-w-3xl border-primary/20">
        <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
          <BookOpen className="w-5 h-5" />
          Infographic — key ideas
        </h2>
        <ul className="list-disc ml-5 space-y-1 text-sm text-muted-foreground mb-4">
          {topic.infographicBullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
        <div className="grid sm:grid-cols-2 gap-3">
          {topic.formulas.map((f) => (
            <div key={f.name} className="rounded-lg border bg-muted/30 p-3">
              <p className="text-xs font-medium text-muted-foreground">{f.name}</p>
              <p className="font-mono text-sm mt-1">{f.latex}</p>
              {f.note ? <p className="text-xs text-muted-foreground mt-1">{f.note}</p> : null}
            </div>
          ))}
        </div>
      </Card>

      <Card className="gloss-panel p-6 max-w-3xl">
        <h2 className="text-lg font-semibold mb-3">Read — formula sheet</h2>
        <div className="space-y-4">
          {topic.readSections.map((s) => (
            <div key={s.title}>
              <h3 className="font-medium text-sm">{s.title}</h3>
              <p className="text-sm text-muted-foreground mt-1">{s.body}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="flex flex-wrap gap-3 max-w-3xl">
        <Button asChild>
          <Link to={`/math-tutor/practice/${topic.id}`}>
            <PenLine className="w-4 h-4 mr-2" />
            Practice ({topic.questionCount} questions)
          </Link>
        </Button>
        <Button variant="outline" asChild>
          <Link to="/math-tutor/reports">
            <BarChart3 className="w-4 h-4 mr-2" />
            Topic reports
          </Link>
        </Button>
      </div>
    </div>
  );
}
