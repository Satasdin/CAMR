package io.github.satasdin.camr.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pure-JVM tests of the ported engine logic (the same behaviour as camr/memory in Python). */
class EngineLogicTest {
    @Test fun tokenCountMatchesTheDesktopRegex() = assertEquals(8, Tokens.count("Walter West directed it, in 1921."))

    @Test fun shortTextIsOneChunk() = assertEquals(listOf("a b c"), Tokens.chunk("a  b\nc"))

    @Test fun longTextIsChunkedWithOverlap() {
        val text = (1..300).joinToString(" ") { "w$it" }
        val chunks = Tokens.chunk(text, size = 120, overlap = 16)
        assertEquals(3, chunks.size)
        assertTrue(chunks[1].startsWith("w105 "))  // 120 - 16 = 104 words step
        assertTrue(chunks.last().endsWith("w300"))
    }

    @Test fun groundedShare() {
        assertEquals(1.0, CamrEngine.groundedShare("Walter West", "The film was directed by Walter West.")!!, 1e-9)
        assertEquals(0.0, CamrEngine.groundedShare("John Sturges", "The film was directed by Walter West.")!!, 1e-9)
        assertNull(CamrEngine.groundedShare("the", "anything"))
    }

    @Test fun dotOfUnitVectors() = assertEquals(1f, CamrEngine.dot(normalise(floatArrayOf(3f, 4f)), normalise(floatArrayOf(3f, 4f))), 1e-6f)

    @Test fun blobRoundTrip() {
        val v = floatArrayOf(0.1f, -2f, 3.5f)
        assertTrue(v.contentEquals(MemoryStore.fromBlob(MemoryStore.toBlob(v))))
    }
}
