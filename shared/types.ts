// 前后端共享类型契约（与 backend/app/schemas/novel.py 一一对应）
export interface NovelCreate { title: string; genre: string; premise: string; target_chapters: number; style: string }
export interface NovelOut extends NovelCreate { id: string; created_at: string }
export interface ChapterOutline { chapter: number; title: string; hook: string; climax: string; word_count: number }
export interface VolumeOutline { volume: string; chapters: ChapterOutline[] }
export interface ChapterGenerateResponse { novel_id: string; chapter_no: number; title: string; content: string; word_count: number; retrieved_context: string[] }
export interface ChapterReviewResponse { novel_id: string; chapter_no: number; score: number; issues: string[]; suggestion: string }
export interface CharacterState { name: string; role: string; personality: string; motivation: string; current_status: string; growth_arc: string }
export interface ForeshadowItem { id: string; description: string; planted_chapter: number; status: string }
export interface MemorySnapshot { novel_id: string; characters: CharacterState[]; foreshadows: ForeshadowItem[]; recent_chapter_summaries: string[]; stage_summaries: string[] }
