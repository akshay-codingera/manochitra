import asyncio
from playwright.async_api import async_playwright

async def verify_live():
    print('Testing live deployment at https://manochitra.vercel.app ...')
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1600, 'height': 1100})
        
        # 1. Load live page
        resp = await page.goto('https://manochitra.vercel.app', wait_until='networkidle', timeout=20000)
        print(f'Live HTTP status: {resp.status}')
        assert resp.status == 200, f'Expected 200, got {resp.status}'
        
        # 2. Check title and heading
        title = await page.title()
        heading = await page.locator('#hero-title').text_content()
        print(f'Page title: {title}')
        print(f'Heading: {heading}')
        assert 'manochitra' in title.lower()
        assert '5 Diagrams' in heading
        
        # 3. Check concept rows
        rows = await page.locator('#results-body tr').all()
        print(f'Concept rows loaded: {len(rows)}')
        assert len(rows) >= 5
        
        # 4. Check cost formatting
        cost = await page.locator('.usage-cost').first.text_content()
        free_tier = await page.locator('.usage-free-tier').first.text_content()
        print(f'Row 1 Cost: {cost}, Free tier: {free_tier}')
        assert '$0.' in cost
        assert '$0.00' in free_tier
        
        # 5. Reviewer interactions: Note + Approve on row 1
        row1 = page.locator('#results-body tr').nth(0)
        await row1.locator('.review-note-input').fill('Verified on live Vercel production.')
        await row1.locator('.review-btn.approve').click()
        await page.wait_for_timeout(400)
        status1 = await row1.locator('.review-decision-badge').text_content()
        print(f'Row 1 approved: {status1.strip()}')
        assert 'ACCEPTED' in status1
        
        # Reject on row 2
        row2 = page.locator('#results-body tr').nth(1)
        await row2.locator('.review-note-input').fill('Tested live rejection feedback.')
        await row2.locator('.review-btn.reject').click()
        await page.wait_for_timeout(400)
        status2 = await row2.locator('.review-decision-badge').text_content()
        print(f'Row 2 rejected: {status2.strip()}')
        assert 'REJECTED' in status2
        
        # 6. Check metrics updated
        acc = await page.locator('#metric-accepted').text_content()
        rej = await page.locator('#metric-rejected').text_content()
        print(f'Live metrics: Accepted={acc}, Rejected={rej}')
        assert acc == '1' and rej == '1'
        
        # 7. Reload and verify persistence
        print('Reloading live site to verify LocalStorage persistence...')
        await page.reload(wait_until='networkidle')
        await page.wait_for_selector('#results-body tr', timeout=15000)
        
        row1_reloaded = page.locator('#results-body tr').nth(0)
        status1_reloaded = await row1_reloaded.locator('.review-decision-badge').text_content()
        note1_reloaded = await row1_reloaded.locator('.review-note-input').input_value()
        print(f'Row 1 after live reload: status={status1_reloaded.strip()}, note={note1_reloaded}')
        assert 'ACCEPTED' in status1_reloaded
        assert 'Verified on live Vercel' in note1_reloaded
        
        # 8. Check IndexedDB Archive on live site
        archive_cards = await page.locator('.archive-grid .archive-card').all()
        print(f'Live archive cards found: {len(archive_cards)}')
        assert len(archive_cards) >= 2
        
        # 9. Test Theme switcher on live site
        theme_toggle = page.locator('#theme-toggle')
        await theme_toggle.click()
        await page.wait_for_timeout(400)
        theme = await page.evaluate("() => document.documentElement.getAttribute('data-theme')")
        print(f'Theme toggled to: {theme}')
        assert theme == 'dark'
        
        await browser.close()
        print('LIVE VERCEL VERIFICATION COMPLETED SUCCESSFULLY.')

if __name__ == '__main__':
    asyncio.run(verify_live())
