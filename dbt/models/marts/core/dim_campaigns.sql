select
    campaign_id,
    campaign_name,
    channel,
    case channel
        when 'google_ads' then 'Google Ads'
        when 'meta_ads' then 'Meta (Facebook/Instagram)'
        when 'tiktok_ads' then 'TikTok Ads'
        when 'newsletter' then 'Newsletter'
        when 'affiliate' then 'Afiliacja'
    end                                               as channel_name,
    channel in ('google_ads', 'meta_ads', 'tiktok_ads') as is_paid_media,
    campaign_type,
    start_date,
    end_date,
    end_date - start_date + 1                         as duration_days,
    daily_budget,
    discount_pct,
    target_category
from {{ ref('stg_campaigns') }}
