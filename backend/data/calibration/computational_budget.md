19:17 25.01.2026// GrantPilot AI - Data Ingestion API
// POST /api/admin/ingest - Trigger data ingestion from a source
// GET /api/admin/ingest - Get ingestion statistics

import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { ingestionService } from '@/lib/ingestion/ingestion-service';
import { z } from 'zod';

const IngestRequestSchema = z.object({
  source: z.enum(['manual_entry', 'college_scorecard', 'studyportals', 'daad']),
  options: z.record(z.unknown()).optional(),
});

export async function POST(request: Request) {
  try {
    // Check authentication - only allow admin users
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // For now, allow any authenticated user to trigger ingestion
    // In production, add admin role check
    
    const body = await request.json();
    const { source, options } = IngestRequestSchema.parse(body);

    // Run ingestion
    const result = await ingestionService.ingestFromSource(source, options);

    return NextResponse.json({
      success: result.success,
      message: result.success ? 'Ingestion completed successfully' : 'Ingestion completed with errors',
      data: {
        batchId: result.batchId,
        universitiesProcessed: result.universitiesProcessed,
        universitiesAdded: result.universitiesAdded,
        universitiesUpdated: result.universitiesUpdated,
        programsAdded: result.programsAdded,
        scholarshipsAdded: result.scholarshipsAdded,
        durationMs: result.duration,
        errors: result.errors.length > 0 ? result.errors : undefined,
      },
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json({ error: 'Invalid request', details: error.errors }, { status: 400 });
    }
    
    console.error('[GrantPilot] Ingestion error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Ingestion failed' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const stats = await ingestionService.getStats();

    return NextResponse.json({
      success: true,
      data: stats,
    });
  } catch (error) {
    console.error('[GrantPilot] Stats error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to get stats' },
      { status: 500 }
    );
  }
}
